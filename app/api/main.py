from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hashlib import sha1
import logging

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.infra import formatter
from app.agents import build_decision_packet, build_fallback_packet
from app.ai_client import mock_ai_decision
from app.agents.coach_agent import build_coach_output, build_prompt, can_call_ai
from app.config import get_settings
from app.engines.hard_rules import evaluate_hard_rules
from app.engines.news_timing import compute_news_timing
from app.agents.news_agent import get_lock
from app.infra.db import (
    add_ai_usage,
    get_ai_usage,
    get_conn,
    init_db,
    insert_ai_message,
    insert_signal,
    to_json,
    was_alert_sent,
    was_telegram_sent,
)
from app.infra.telegram_sender import TelegramSender
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    BlockedBy,
    DecisionAIOutput,
    DecisionResult,
    DecisionStatus,
    Quality,
)
from app.providers import get_provider
from app.engines.scorer import score_packet
from app.state_repo import get_today_state, is_cooldown_ok, update_on_decision
from app.api.runner import router as runner_router
from app.api.outcomes import router as outcomes_router

# Patterns à bloquer (anti-scanners) - path.startswith ou path ==
_BLOCKED_PREFIXES = ("/.env", "/.git", "/.aws", "/.ssh", "/.htaccess", "/.htpasswd")
_BLOCKED_EXACT = (
    "/wp-config.php", "/docker-compose.yml", "/config.json",
    "/phpmyadmin", "/admin.php", "/.env", "/.git",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings = get_settings()
    if settings.market_provider == "remote_mt5" and settings.mt5_bridge_url:
        url = settings.mt5_bridge_url.rstrip("/") + "/health"
        try:
            resp = httpx.get(url, timeout=3.0)
            if resp.status_code != 200:
                logging.warning("DATA_OFF bridge unreachable: status %s", resp.status_code)
        except Exception:  # noqa: BLE001
            logging.warning("DATA_OFF bridge unreachable")
    yield


app = FastAPI(title="Trader Assistant API", version="0.1.0", lifespan=lifespan)
app.include_router(runner_router)
app.include_router(outcomes_router)


@app.middleware("http")
async def block_scanner_paths(request, call_next):
    path = request.url.path
    path_lower = path.lower()
    for p in _BLOCKED_PREFIXES:
        if path_lower.startswith(p):
            logging.warning("Blocked scanner path: %s", request.url.path)
            from starlette.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
    for p in _BLOCKED_EXACT:
        if path_lower == p or path_lower == p + "/":
            logging.warning("Blocked scanner path: %s", request.url.path)
            from starlette.responses import JSONResponse
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if "wp-config" in path_lower or path_lower in ("/config.json", "/config.json/"):
        logging.warning("Blocked scanner path: %s", request.url.path)
        from starlette.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)


class TelegramTestRequest(BaseModel):
    text: str | None = None


class CoachPreviewRequest(BaseModel):
    symbol: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    settings = get_settings()
    provider = get_provider()
    symbol = payload.symbol or settings.symbol_default
    data_off = False
    data_off_reason = None
    try:
        packet = build_decision_packet(provider, symbol)
    except Exception as exc:  # noqa: BLE001 - on veut marquer DATA_OFF
        packet = build_fallback_packet(symbol)
        data_off = True
        data_off_reason = str(exc)
    if not data_off and packet.data_latency_ms > settings.data_max_age_sec * 1000:
        data_off = True
        data_off_reason = "Data trop ancienne"
    score_total, reasons = score_packet(packet)
    packet.score_rules = score_total
    packet.reasons_rules = reasons

    status = DecisionStatus.go
    blocked_by = None
    why = reasons[:3]
    now_utc = datetime.fromisoformat(packet.timestamps["ts_utc"])
    day_paris = packet.timestamps["ts_paris"].split("T")[0]
    state = get_today_state(day_paris)
    cooldown_ok = is_cooldown_ok(state, now_utc)
    packet.state = {
        "daily_budget_used": state.daily_loss_amount,
        "cooldown_ok": cooldown_ok,
        "last_signal_key": state.last_signal_key,
        "consecutive_losses": state.consecutive_losses,
    }

    signal_key = sha1(f"{symbol}:{packet.timestamps['ts_utc']}".encode("utf-8")).hexdigest()
    if data_off:
        status = DecisionStatus.no_go
        blocked_by = BlockedBy.data_off
        packet.reasons_rules = ["Données marché indisponibles"]
        why = ["Données marché indisponibles"]
    else:
        hard_rule = evaluate_hard_rules(packet, state, signal_key, now_utc)
        if hard_rule.blocked_by:
            status = DecisionStatus.no_go
            blocked_by = hard_rule.blocked_by
            why = [hard_rule.reason] if hard_rule.reason else ["Hard rule KO"]
        elif score_total < 80:
            status = DecisionStatus.no_go
            blocked_by = BlockedBy.no_setup
            why = ["Score insuffisant"]

    quality = Quality.a_plus if score_total >= 90 else Quality.a if score_total >= 80 else Quality.b
    confidence = min(100, max(50, score_total))
    score_effective = 0 if status == DecisionStatus.no_go and blocked_by else score_total

    ai_output = None
    ai_latency_ms = None
    ai_model = None
    ai_input_tokens = 0
    ai_output_tokens = 0
    ai_cost_usd = 0.0
    if settings.ai_enabled and settings.telegram_enabled:
        ai_output = mock_ai_decision()
        ai_latency_ms = 200
        if status == DecisionStatus.no_go:
            ai_output = DecisionAIOutput(
                decision=DecisionStatus.no_go,
                confidence=ai_output.confidence,
                quality=ai_output.quality,
                why=ai_output.why,
                notes="Hard rules KO",
            )

    decision = DecisionResult(
        status=status,
        blocked_by=blocked_by,
        score_total=score_total,
        score_effective=score_effective,
        confidence=confidence,
        quality=quality,
        why=why,
    )

    telegram_sent = 0
    telegram_error = None
    telegram_latency_ms = None
    sender = TelegramSender()
    important_blocks = {
        item.strip().upper()
        for item in settings.telegram_no_go_important_blocks.split(",")
        if item.strip()
    }
    should_send = False
    if status == DecisionStatus.go:
        should_send = True
    elif (
        status == DecisionStatus.no_go
        and blocked_by
        and settings.telegram_send_no_go_important
        and blocked_by.value in important_blocks
    ):
        should_send = True

    if should_send and blocked_by == BlockedBy.duplicate_signal:
        should_send = False
    if should_send and was_telegram_sent(signal_key):
        should_send = False

    raw_message = formatter.format_message(
        symbol=symbol,
        decision=decision,
        entry=packet.proposed_entry,
        sl=packet.sl,
        tp1=packet.tp1,
        tp2=packet.tp2,
        direction=packet.direction,
    )
    now_utc_str = packet.timestamps["ts_utc"]
    mt5_ts = packet.timestamps.get("ts_paris") or now_utc_str
    message = raw_message
    if settings.ai_enabled and should_send:
        try:
            coach_payload = {
                "mode": "DECISION",
                "decision": decision.model_dump(),
                "packet": packet.model_dump(),
                "news_state": packet.news_state,
                "context_summary": packet.context_summary,
                "raw_message": raw_message,
            }
            prompt = build_prompt(coach_payload)
            date = now_utc_str[:10]
            if can_call_ai(date, prompt):
                coach_output = build_coach_output(coach_payload)
                if coach_output.telegram_text:
                    message = coach_output.telegram_text
                    if status == DecisionStatus.go:
                        title = formatter.format_go_title(symbol, packet.direction)
                        lines = message.strip().split("\n")
                        lines[0] = title
                        message = "\n".join(lines)
                ai_model = coach_output.model
                ai_input_tokens += coach_output.input_tokens
                ai_output_tokens += coach_output.output_tokens
                ai_cost_usd += coach_output.cost_usd
                ai_latency_ms = coach_output.latency_ms
                ai_output = DecisionAIOutput(
                    decision=decision.status,
                    confidence=decision.confidence,
                    quality=decision.quality,
                    why=decision.why,
                    notes=coach_output.risk_note or None,
                )
                add_ai_usage(
                    date,
                    coach_output.input_tokens,
                    coach_output.output_tokens,
                    coach_output.cost_usd,
                    coach_output.cost_eur,
                )
                insert_ai_message(
                    mt5_ts,
                    symbol,
                    decision.status.value,
                    coach_output.telegram_text,
                    to_json(
                        {
                            "mode": "DECISION",
                            "news_state": packet.news_state,
                            "context_summary": packet.context_summary,
                            "model": coach_output.model,
                        }
                    ),
                )
        except Exception:  # noqa: BLE001
            message = raw_message

    prealert_text = None
    alert_key = None
    if packet.news_state.get("should_pre_alert") and packet.news_state.get("bucket_label"):
        event_dt = packet.news_state.get("next_event", {}).get("datetime_iso")
        candidate_key = f"prealert:{event_dt}:{packet.news_state.get('bucket_label')}"
        if not was_alert_sent(candidate_key):
            alert_key = candidate_key
            prealert_text = formatter.format_prealert(symbol, packet.news_state)
            if settings.ai_enabled:
                try:
                    coach_payload = {
                        "mode": "PRE_ALERT",
                        "decision": decision.model_dump(),
                        "packet": packet.model_dump(),
                        "news_state": packet.news_state,
                        "context_summary": packet.context_summary,
                        "raw_message": prealert_text,
                    }
                    prompt = build_prompt(coach_payload)
                    date = now_utc_str[:10]
                    if can_call_ai(date, prompt):
                        coach_output = build_coach_output(coach_payload)
                        if coach_output.telegram_text:
                            prealert_text = coach_output.telegram_text
                        ai_model = coach_output.model
                        ai_input_tokens += coach_output.input_tokens
                        ai_output_tokens += coach_output.output_tokens
                        ai_cost_usd += coach_output.cost_usd
                        ai_latency_ms = coach_output.latency_ms
                        add_ai_usage(
                            date,
                            coach_output.input_tokens,
                            coach_output.output_tokens,
                            coach_output.cost_usd,
                            coach_output.cost_eur,
                        )
                        insert_ai_message(
                            mt5_ts,
                            symbol,
                            "PRE_ALERT",
                            coach_output.telegram_text,
                            to_json(
                                {
                                    "mode": "PRE_ALERT",
                                    "news_state": packet.news_state,
                                    "context_summary": packet.context_summary,
                                    "model": coach_output.model,
                                }
                            ),
                        )
                except Exception:  # noqa: BLE001
                    pass

    if should_send and settings.telegram_enabled:
        result = sender.send_message(message)
        telegram_sent = 1 if result.sent else 0
        telegram_error = result.error
        telegram_latency_ms = result.latency_ms
    if prealert_text and settings.telegram_enabled:
        sender.send_message(prealert_text)

    insert_signal(
        {
            "ts_utc": mt5_ts,
            "symbol": symbol,
            "tf_signal": settings.tf_signal,
            "tf_context": settings.tf_context,
            "status": decision.status.value,
            "blocked_by": decision.blocked_by.value if decision.blocked_by else None,
            "direction": packet.direction,
            "entry": packet.proposed_entry,
            "sl": packet.sl,
            "tp1": packet.tp1,
            "tp2": packet.tp2,
            "rr_tp2": packet.rr_tp2,
            "score_total": score_total,
            "score_effective": score_effective,
            "telegram_sent": telegram_sent,
            "telegram_error": telegram_error,
            "telegram_latency_ms": telegram_latency_ms,
            "alert_key": alert_key,
            "score_rules_json": to_json({"score": score_total, "reasons": packet.reasons_rules}),
            "ai_enabled": 1 if settings.ai_enabled else 0,
            "ai_output_json": to_json(
                ai_output.model_dump() if hasattr(ai_output, "model_dump") else ai_output
            ),
            "ai_model": ai_model,
            "ai_input_tokens": ai_input_tokens,
            "ai_output_tokens": ai_output_tokens,
            "ai_cost_usd": ai_cost_usd,
            "decision_packet_json": to_json(packet.model_dump()),
            "signal_key": signal_key,
            "reasons_json": to_json({"why": why}),
            "message": message,
            "data_latency_ms": packet.data_latency_ms,
            "ai_latency_ms": ai_latency_ms,
        }
    )
    if status == DecisionStatus.go:
        update_on_decision(day_paris, signal_key, now_utc_str)

    return AnalyzeResponse(
        decision=decision,
        message=message,
        decision_packet=packet,
        ai_output=ai_output,
        ai_enabled=settings.ai_enabled,
        data_latency_ms=packet.data_latency_ms,
        ai_latency_ms=ai_latency_ms,
        signal_key=signal_key,
    )


@app.post("/telegram/test")
def telegram_test(
    payload: TelegramTestRequest | None = None,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    settings = get_settings()
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not settings.telegram_chat_id:
        raise HTTPException(status_code=400, detail="TELEGRAM_CHAT_ID manquant")
    message = payload.text if payload and payload.text else "Test Telegram ✅"
    result = TelegramSender().send_message(message)
    return {"sent": result.sent, "latency_ms": result.latency_ms, "error": result.error}


@app.get("/stats/ai_cost")
def ai_cost_stats(date: str, x_admin_token: str | None = Header(default=None, alias="X-Admin-Token")) -> dict:
    settings = get_settings()
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    usage = get_ai_usage(date)
    return {
        "date": date,
        "total_calls": usage["n_calls"],
        "total_cost_usd": float(usage["cost_usd"]),
        "total_cost_eur": float(usage["cost_eur"]),
        "total_input_tokens": int(usage["tokens_in"]),
        "total_output_tokens": int(usage["tokens_out"]),
    }


@app.get("/news/next")
def news_next() -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    locked, next_event, provider_ok, raw_count, lock_window = get_lock(
        now,
        settings.news_lock_high_pre_min,
        settings.news_lock_high_post_min,
        settings.news_lock_med_pre_min,
        settings.news_lock_med_post_min,
    )
    timing = compute_news_timing(
        now,
        next_event,
        settings.news_lock_high_pre_min,
        settings.news_lock_high_post_min,
        settings.news_lock_med_pre_min,
        settings.news_lock_med_post_min,
        settings.news_prealert_minutes,
    )
    return {
        "provider": settings.news_provider,
        "ts_now": now.isoformat(),
        "next_event": (
            {
                "title": next_event.title,
                "impact": next_event.impact,
                "datetime_iso": next_event.datetime_iso,
                "country": next_event.country,
                "currency": next_event.currency,
            }
            if next_event
            else None
        ),
        "lock_window_start_min": lock_window[0],
        "lock_window_end_min": lock_window[1],
        "news_lock": timing.lock_active,
        "raw_count": raw_count,
        "provider_ok": provider_ok,
    }


@app.post("/coach/preview")
def coach_preview(
    payload: CoachPreviewRequest | None = None,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    settings = get_settings()
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    provider = get_provider()
    symbol = payload.symbol if payload and payload.symbol else settings.symbol_default
    packet = build_decision_packet(provider, symbol)
    score_total, reasons = score_packet(packet)
    packet.score_rules = score_total
    packet.reasons_rules = reasons

    status = DecisionStatus.go
    blocked_by = None
    why = reasons[:3]
    now_utc = datetime.fromisoformat(packet.timestamps["ts_utc"])
    state = get_today_state(packet.timestamps["ts_paris"].split("T")[0])
    hard_rule = evaluate_hard_rules(packet, state, "preview", now_utc)
    if hard_rule.blocked_by:
        status = DecisionStatus.no_go
        blocked_by = hard_rule.blocked_by
        why = [hard_rule.reason] if hard_rule.reason else ["Hard rule KO"]
    elif score_total < 80:
        status = DecisionStatus.no_go
        blocked_by = BlockedBy.no_setup
        why = ["Score insuffisant"]

    decision = DecisionResult(
        status=status,
        blocked_by=blocked_by,
        score_total=score_total,
        score_effective=0 if status == DecisionStatus.no_go and blocked_by else score_total,
        confidence=min(100, max(50, score_total)),
        quality=Quality.a_plus if score_total >= 90 else Quality.a if score_total >= 80 else Quality.b,
        why=why,
    )

    raw_message = formatter.format_message(
        symbol=symbol,
        decision=decision,
        entry=packet.proposed_entry,
        sl=packet.sl,
        tp1=packet.tp1,
        tp2=packet.tp2,
        direction=packet.direction,
    )

    message = raw_message
    ai_meta = None
    if settings.ai_enabled:
        try:
            coach_payload = {
                "mode": "PREVIEW",
                "decision": decision.model_dump(),
                "packet": packet.model_dump(),
                "news_state": packet.news_state,
                "context_summary": packet.context_summary,
                "raw_message": raw_message,
            }
            prompt = build_prompt(coach_payload)
            date = packet.timestamps["ts_utc"][:10]
            if can_call_ai(date, prompt):
                coach_output = build_coach_output(coach_payload)
                if coach_output.telegram_text:
                    message = coach_output.telegram_text
                add_ai_usage(
                    date,
                    coach_output.input_tokens,
                    coach_output.output_tokens,
                    coach_output.cost_usd,
                    coach_output.cost_eur,
                )
                insert_ai_message(
                    packet.timestamps.get("ts_paris") or packet.timestamps["ts_utc"],
                    symbol,
                    decision.status.value,
                    coach_output.telegram_text,
                    to_json(
                        {
                            "mode": "PREVIEW",
                            "news_state": packet.news_state,
                            "context_summary": packet.context_summary,
                            "model": coach_output.model,
                        }
                    ),
                )
                ai_meta = {
                    "model": coach_output.model,
                    "tokens_in": coach_output.input_tokens,
                    "tokens_out": coach_output.output_tokens,
                    "cost_usd": coach_output.cost_usd,
                    "cost_eur": coach_output.cost_eur,
                }
        except Exception:  # noqa: BLE001
            message = raw_message

    return {
        "decision": decision.model_dump(),
        "message": message,
        "ai_meta": ai_meta,
    }
