from __future__ import annotations

from pathlib import Path

_env_local = Path(__file__).resolve().parents[2] / ".env.local"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local)
    except ImportError:
        pass

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from hashlib import sha1
import logging
import time

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from app.infra import formatter
from app.agents import build_decision_packet, build_fallback_packet
from app.ai_client import mock_ai_decision
from app.agents.coach_agent import build_coach_output, build_prompt, can_call_ai
from app.config import get_settings
from app.engines.hard_rules import evaluate_hard_rules
from app.engines.news_timing import compute_news_timing
from app.agents.news_agent import get_lock
from app.engines.suivi_engine import build_suivi_situation_message, evaluate_suivi
from app.infra.db import (
    add_ai_usage,
    clear_active_trade,
    get_ai_usage,
    get_stats_summary,
    get_conn,
    get_active_trade,
    get_last_analyze_ts,
    get_last_trade_closed_ts,
    get_last_suivi_sortie_active_started_ts,
    get_trade_outcomes_today,
    record_trade_outcome,
    get_last_go_sent_today,
    get_last_suivi_alerte_ts,
    get_last_telegram_sent_ts,
    init_db,
    insert_ai_message,
    insert_signal,
    set_active_trade,
    set_last_suivi_alerte_ts,
    set_last_suivi_sortie_sent,
    set_daily_summary_sent,
    set_data_off_alert_sent,
    set_last_suivi_situation_ts,
    set_suivi_maintien_sent,
    to_json,
    was_alert_sent,
    was_data_off_alert_sent_today,
    clear_data_off_alert_sent,
    was_daily_summary_sent,
    was_suivi_maintien_sent,
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
from app.state_repo import get_today_state, is_cooldown_ok, update_on_decision, update_setup_context

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings = get_settings()
    logging.info("MARKET_PROVIDER=%s (prix = MT5 live si remote_mt5, sinon mock)", settings.market_provider)
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

# Middleware : bloquer les accès aux chemins sensibles
BLOCKED_PATHS = {".env", ".git", ".env.local", "env", "config.py", "secrets"}


@app.middleware("http")
async def block_sensitive_paths(request, call_next):
    path = (request.url.path or "").lower().strip("/")
    for blocked in BLOCKED_PATHS:
        if blocked in path or path.startswith(blocked) or f"/{blocked}" in f"/{path}":
            raise HTTPException(status_code=404, detail="Not Found")
    return await call_next(request)


class TelegramTestRequest(BaseModel):
    text: str | None = None


class CoachPreviewRequest(BaseModel):
    symbol: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/runner/status")
def runner_status() -> dict:
    """Statut pour le runner : dernière analyse, dernière alerte Telegram."""
    last_analyze = get_last_analyze_ts()
    last_telegram = get_last_telegram_sent_ts()
    return {
        "status": "ok",
        "last_analyze_ts": last_analyze,
        "last_telegram_sent_ts": last_telegram,
    }


@app.get("/data-status")
def data_status() -> dict:
    """
    Vérifie si les données marché sont disponibles (bridge MT5, latence).
    Utile pour diagnostiquer DATA_OFF : data_ok=false + data_off_reason indiquent la cause.
    """
    settings = get_settings()
    data_ok = True
    data_off_reason = None
    data_latency_ms = None
    bridge_reachable = None
    try:
        provider = get_provider()
        if settings.market_provider == "remote_mt5" and settings.mt5_bridge_url:
            url = settings.mt5_bridge_url.rstrip("/") + "/health"
            try:
                resp = httpx.get(url, timeout=3.0)
                bridge_reachable = resp.status_code == 200
                if not bridge_reachable:
                    data_ok = False
                    data_off_reason = f"Bridge HTTP {resp.status_code}"
            except Exception as e:  # noqa: BLE001
                bridge_reachable = False
                data_ok = False
                data_off_reason = f"Bridge unreachable: {e!s}"
        if data_ok:
            packet = build_decision_packet(provider, settings.symbol_default)
            data_latency_ms = packet.data_latency_ms
            if data_latency_ms > settings.data_max_age_sec * 1000:
                data_ok = False
                data_off_reason = "Data trop ancienne"
    except Exception as exc:  # noqa: BLE001
        data_ok = False
        data_off_reason = str(exc)
    return {
        "data_ok": data_ok,
        "data_off_reason": data_off_reason,
        "data_latency_ms": data_latency_ms,
        "data_max_age_sec": settings.data_max_age_sec,
        "bridge_reachable": bridge_reachable,
        "market_provider": settings.market_provider,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    settings = get_settings()
    provider = get_provider()
    symbol = payload.symbol or settings.symbol_default
    # Suivi en priorité : si trade actif, fetch tick+candles M15 et exécuter suivi AVANT le build packet.
    # Évite que timeout/erreur M5 ou autre bloque l'envoi "Bravo TP1/SL" sur Telegram.
    now_utc = datetime.now(timezone.utc)
    day_paris = now_utc.astimezone(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    active = get_active_trade(day_paris)
    tick_bid, tick_ask = None, None
    candles_for_suivi = None
    if active:
        try:
            if hasattr(provider, "get_tick"):
                tick = provider.get_tick(symbol)
                if tick:
                    tick_bid = float(tick[0])
                    tick_ask = float(tick[1]) if len(tick) > 1 else tick_bid
            candles_for_suivi = provider.get_candles(symbol, settings.tf_signal, 80)
        except Exception as e:  # noqa: BLE001
            log.warning("Suivi préalable (tick/candles): %s", e)
        if tick_bid is not None and candles_for_suivi:
            dir_suivi = (active["active_direction"] or "BUY").upper()
            price_for_suivi = float(tick_ask) if dir_suivi == "SELL" and tick_ask is not None else float(tick_bid)
            suivi_pre = evaluate_suivi(
                price_for_suivi,
                active["active_direction"] or "BUY",
                float(active["active_entry"]),
                float(active["active_sl"]),
                float(active["active_tp1"]),
                float(active["active_tp2"]),
                "RANGE",
                candles_for_suivi,
                news_state={},
                sr_buffer_points=settings.sr_buffer_points,
                active_started_ts=active.get("active_started_ts"),
            )
            if suivi_pre.closed:
                already_sent = get_last_suivi_sortie_active_started_ts(day_paris) == active.get("active_started_ts")
                if not already_sent and settings.telegram_enabled:
                    sender = TelegramSender()
                    result = sender.send_message(suivi_pre.message)
                    if not result.sent:
                        log.warning("Telegram SORTIE (suivi préalable) non envoyé: %s", result.error)
                    else:
                        set_last_suivi_sortie_sent(day_paris, active.get("active_started_ts"))
                if getattr(suivi_pre, "outcome_pips", None) is not None:
                    record_trade_outcome(day_paris, suivi_pre.outcome_pips)
                clear_active_trade(day_paris, closed_ts=now_utc.isoformat())
                log.info("Trade clôturé (TP/SL suivi préalable): outcome_pips=%s", getattr(suivi_pre, "outcome_pips", None))

    data_off = False
    data_off_reason = None
    try:
        packet = build_decision_packet(provider, symbol)
    except Exception as exc:  # noqa: BLE001 - on veut marquer DATA_OFF
        err_str = str(exc).lower()
        if any(x in err_str for x in ("bridge", "connection", "timeout", "mt5", "refused", "unreachable")):
            for _ in range(2):
                time.sleep(2)
                try:
                    packet = build_decision_packet(provider, symbol)
                    break
                except Exception as exc2:  # noqa: BLE001
                    exc = exc2
            else:
                packet = build_fallback_packet(symbol)
                data_off = True
                data_off_reason = str(exc)
        else:
            packet = build_fallback_packet(symbol)
            data_off = True
            data_off_reason = str(exc)
    now_utc = datetime.fromisoformat(packet.timestamps["ts_utc"])
    day_paris = packet.timestamps["ts_paris"].split("T")[0]
    current_price = None
    if tick_bid is not None and tick_ask is not None:
        current_price = tick_bid
    elif hasattr(provider, "get_tick"):
        tick = provider.get_tick(symbol)
        if tick:
            tick_bid = float(tick[0])
            tick_ask = float(tick[1]) if len(tick) > 1 else tick_bid
            current_price = tick_bid
    active = get_active_trade(day_paris)

    # Suivi : soit données OK, soit retry si data_off et trade actif (on a déjà traité SORTIE en préalable si actif)
    candles = candles_for_suivi
    if candles is None and not data_off:
        try:
            candles = provider.get_candles(symbol, settings.tf_signal, 80)
        except Exception:  # noqa: BLE001
            pass
    elif candles is None and data_off and active:
        try:
            tick_retry = provider.get_tick(symbol) if hasattr(provider, "get_tick") else None
            candles_retry = provider.get_candles(symbol, settings.tf_signal, 80)
            if tick_retry and candles_retry:
                if tick_bid is None:
                    tick_bid = float(tick_retry[0])
                    tick_ask = float(tick_retry[1]) if len(tick_retry) > 1 else tick_bid
                current_price = float(tick_retry[0])
                candles = candles_retry
                data_off = False
        except Exception:  # noqa: BLE001
            pass

    if not active:
        pass  # pas de trade actif
    elif current_price is None:
        log.info("Suivi skippé: trade actif mais prix indisponible (tick)")
    elif data_off:
        log.info("Suivi skippé: trade actif mais data_off (pas de bougies/prix après retry)")
    elif candles is None:
        log.info("Suivi skippé: trade actif mais bougies indisponibles")
    else:
        # Prix pour suivi: BID si BUY (on vend pour clôturer), ASK si SELL (on achète pour clôturer)
        dir_suivi = (active["active_direction"] or "BUY").upper()
        price_for_suivi = float(tick_ask) if dir_suivi == "SELL" and tick_ask is not None else (float(tick_bid) if tick_bid is not None else current_price)
        log.debug(
            "Suivi: prix=%s (bid=%s ask=%s) dir=%s entry=%s tp1=%s sl=%s",
            round(price_for_suivi, 2), tick_bid, tick_ask, dir_suivi,
            round(float(active["active_entry"]), 2), round(float(active["active_tp1"]), 2), round(float(active["active_sl"]), 2),
        )
        suivi = evaluate_suivi(
            price_for_suivi,
            active["active_direction"] or "BUY",
            float(active["active_entry"]),
            float(active["active_sl"]),
            float(active["active_tp1"]),
            float(active["active_tp2"]),
            packet.state.get("structure_h1", "RANGE"),
            candles,
            news_state=packet.news_state,
            sr_buffer_points=settings.sr_buffer_points,
            active_started_ts=active.get("active_started_ts"),
        )
        # SORTIE: immédiat. ALERTE: 1x (pas de relance). MAINTIEN: 1x à mi-chemin TP si critères OK
        send_suivi = False
        entry = float(active["active_entry"])
        tp1 = float(active["active_tp1"])
        dir_suivi = active["active_direction"] or "BUY"
        midpoint = entry + (tp1 - entry) / 2 if dir_suivi == "BUY" else entry - (entry - tp1) / 2
        at_midpoint = (dir_suivi == "BUY" and price_for_suivi >= midpoint) or (dir_suivi == "SELL" and price_for_suivi <= midpoint)
        if suivi.closed:
            already_sent = get_last_suivi_sortie_active_started_ts(day_paris) == active.get("active_started_ts")
            send_suivi = not already_sent
        elif suivi.status == "MAINTIEN" and at_midpoint and not was_suivi_maintien_sent(day_paris):
            send_suivi = True  # MAINTIEN — une seule fois à mi-chemin TP
        elif suivi.status == "ALERTE":
            # Ne pas envoyer l'ALERTE si le trade vient de démarrer (< 5 min) — inutile "Mur/faiblesse" à l'entrée
            duration_min = 0
            started_ts = active.get("active_started_ts")
            if started_ts:
                try:
                    start_dt = datetime.fromisoformat(started_ts)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    nw = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc
                    duration_min = max(0, int((nw - start_dt).total_seconds() / 60))
                except (TypeError, ValueError):
                    pass
            if duration_min >= 5:
                last_alerte = get_last_suivi_alerte_ts(day_paris)
                if last_alerte is None:
                    send_suivi = True  # première (et unique) alerte pour ce trade
        now_paris = now_utc.astimezone(ZoneInfo("Europe/Paris"))
        wd, h, m = now_paris.weekday(), now_paris.hour, now_paris.minute
        is_weekend = (wd == 4 and h >= 23) or (wd == 5) or (wd == 6) or (wd == 0 and h == 0 and m < 1)
        # SORTIE (trade fermé) : toujours envoyer gains/pertes, même hors session ou weekend
        session_ok_or_closed = packet.session_ok and not is_weekend or suivi.closed
        if send_suivi and settings.telegram_enabled and session_ok_or_closed:
            sender = TelegramSender()
            result = sender.send_message(suivi.message)
            if suivi.closed and not result.sent:
                log.warning("Telegram SORTIE non envoyé: %s", result.error)
            if suivi.closed:
                set_last_suivi_sortie_sent(day_paris, active.get("active_started_ts"))
            if suivi.status == "ALERTE" and not suivi.closed:
                set_last_suivi_alerte_ts(day_paris, packet.timestamps["ts_utc"])
            elif suivi.status == "MAINTIEN":
                set_suivi_maintien_sent(day_paris)
        if suivi.closed and send_suivi:
            if getattr(suivi, "outcome_pips", None) is not None:
                record_trade_outcome(day_paris, suivi.outcome_pips)
            clear_active_trade(day_paris, closed_ts=packet.timestamps["ts_utc"])
            log.info("Trade clôturé (TP/SL): outcome_pips=%s", getattr(suivi, "outcome_pips", None))
        # Message situation (durée, prix, tendance, score, analyse, recommandation) au plus toutes les 5 min
        elif not send_suivi and settings.telegram_enabled and packet.session_ok and not is_weekend:
            started_ts = active.get("active_started_ts")
            last_sit = get_last_suivi_situation_ts(day_paris)
            duration_min = 0
            if started_ts:
                try:
                    start_dt = datetime.fromisoformat(started_ts)
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    nw = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc
                    duration_min = max(0, int((nw - start_dt).total_seconds() / 60))
                except (TypeError, ValueError):
                    pass
            send_situation = False
            if last_sit is None:
                send_situation = duration_min >= 1
            else:
                try:
                    last_dt = datetime.fromisoformat(last_sit)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    nw = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc
                    if (nw - last_dt) >= timedelta(minutes=settings.suivi_situation_interval_minutes):
                        send_situation = True
                except (TypeError, ValueError):
                    pass
            if send_situation and duration_min >= 1:
                structure_m15_ok = suivi.status == "MAINTIEN"
                score_sit, _ = score_packet(packet)
                if suivi.status == "MAINTIEN":
                    analysis_summary = "Tout va bien, on est dans le bon sens."
                    recommendation = ""
                elif suivi.status == "ALERTE" and not structure_m15_ok:
                    analysis_summary = "Sens inverse ou résistance, situation a changé."
                    recommendation = "Si bénéfique, fermer. Sinon accepter un peu de dégâts et sortir du trade."
                else:
                    analysis_summary = "Contournement de la situation (zone sensible)."
                    recommendation = ""
                msg_sit = build_suivi_situation_message(
                    dir_suivi,
                    entry,
                    current_price,
                    tp1,
                    float(active["active_sl"]),
                    packet.state.get("structure_h1", "RANGE"),
                    structure_m15_ok,
                    duration_min,
                    score_total=score_sit,
                    analysis_summary=analysis_summary,
                    recommendation=recommendation,
                )
                TelegramSender().send_message(msg_sit)
                set_last_suivi_situation_ts(day_paris, packet.timestamps["ts_utc"])
    if not data_off and packet.data_latency_ms > settings.data_max_age_sec * 1000:
        data_off = True
        data_off_reason = "Data trop ancienne"
    score_total, reasons = score_packet(packet)
    packet.score_rules = score_total
    packet.reasons_rules = reasons

    status = DecisionStatus.go
    blocked_by = None
    why = reasons[:3]
    state = get_today_state(day_paris)
    cooldown_ok = is_cooldown_ok(state, now_utc)
    packet.state = {
        **packet.state,
        "daily_budget_used": state.daily_loss_amount,
        "cooldown_ok": cooldown_ok,
        "last_signal_key": state.last_signal_key,
        "consecutive_losses": state.consecutive_losses,
    }

    signal_key = sha1(f"{symbol}:{packet.timestamps['ts_utc']}".encode("utf-8")).hexdigest()

    setup_confirm_count = 1
    if not data_off and packet.proposed_entry and packet.proposed_entry > 0:
        setup_dir = packet.state.get("setup_direction") or "BUY"
        setup_entry = packet.proposed_entry
        setup_bar_ts = packet.state.get("setup_bar_ts")
        tolerance = settings.setup_entry_tolerance_pts
        min_bars = settings.setup_confirm_min_bars
        last_bar = state.last_setup_bar_ts
        same_setup = (
            state.last_setup_direction == setup_dir
            and state.last_setup_entry is not None
            and abs(setup_entry - state.last_setup_entry) <= tolerance
        )
        if setup_bar_ts != last_bar:
            if same_setup:
                setup_confirm_count = min(state.setup_confirm_count + 1, min_bars)
            else:
                setup_confirm_count = 1
            update_setup_context(day_paris, setup_dir, setup_entry, setup_bar_ts, setup_confirm_count)
        else:
            setup_confirm_count = state.setup_confirm_count

    if data_off:
        status = DecisionStatus.no_go
        blocked_by = BlockedBy.data_off
        reason_text = data_off_reason or "Données marché indisponibles"
        packet.reasons_rules = [reason_text]
        why = [reason_text]
    else:
        hard_rule = evaluate_hard_rules(packet, state, signal_key, now_utc, setup_confirm_count)
        if hard_rule.blocked_by:
            status = DecisionStatus.no_go
            blocked_by = hard_rule.blocked_by
            why = [hard_rule.reason] if hard_rule.reason else ["Hard rule KO"]
        elif score_total < settings.go_min_score:
            status = DecisionStatus.no_go
            blocked_by = BlockedBy.no_setup
            why = ["Score insuffisant"]
        else:
            timing_ready = packet.state.get("timing_ready", False)
            min_bars = settings.setup_confirm_min_bars
            if not timing_ready and setup_confirm_count < min_bars:
                status = DecisionStatus.no_go
                blocked_by = BlockedBy.setup_not_confirmed
                why = [f"En attente du bon moment (zone/pullback) — {setup_confirm_count}/{min_bars} barres"]

    # Données de retour après un DATA_OFF : notifier sur Telegram pour reprendre en temps réel
    if not data_off and settings.telegram_enabled and was_data_off_alert_sent_today(day_paris):
        try:
            TelegramSender().send_message(
                "🟢 Données marché de retour — tu peux reprendre en temps réel."
            )
            clear_data_off_alert_sent(day_paris)
        except Exception:  # noqa: BLE001
            pass

    quality = Quality.a_plus if score_total >= settings.a_plus_min_score else Quality.a if score_total >= settings.go_min_score else Quality.b
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
    now_utc_str = packet.timestamps["ts_utc"]
    current_price = None
    if hasattr(provider, "get_tick"):
        tick = provider.get_tick(symbol)
        if tick:
            current_price = float(tick[0])

    # Calculer should_send AVANT l'appel Coach AI (économie d'API)
    # En suivi (trade actif) : pas de GO ni NO_GO, uniquement MAINTIEN/ALERTE/SORTIE
    if get_active_trade(day_paris):
        should_send = False
        heartbeat_triggered = False
    else:
        important_blocks = {
            item.strip().upper()
            for item in settings.telegram_no_go_important_blocks.split(",")
            if item.strip()
        }
        should_send = False
        heartbeat_triggered = False
        if status == DecisionStatus.go:
            # Ne jamais envoyer sur Telegram un GO qui n'est pas A+ (safeguard prod)
            should_send = score_total >= settings.a_plus_min_score
            # Après un trade clôturé (TP/SL), attendre le bon moment : pas de nouveau GO tout de suite
            last_closed = get_last_trade_closed_ts(day_paris)
            if last_closed:
                try:
                    closed_dt = datetime.fromisoformat(last_closed)
                    if closed_dt.tzinfo is None:
                        closed_dt = closed_dt.replace(tzinfo=timezone.utc)
                    nw = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc
                    if (nw - closed_dt) < timedelta(minutes=settings.cooldown_after_trade_minutes):
                        should_send = False
                except (TypeError, ValueError):
                    pass
            # Ne pas renvoyer le même GO (mêmes niveaux) déjà envoyé récemment
            if should_send:
                last_go = get_last_go_sent_today(day_paris)
                if last_go:
                    try:
                        last_dt = datetime.fromisoformat(last_go["ts_utc"])
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        nw = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc
                        if (nw - last_dt) < timedelta(minutes=60):
                            e, s, t1, t2 = packet.proposed_entry, packet.sl, packet.tp1, packet.tp2
                            le, ls, lt1, lt2 = last_go["entry"], last_go["sl"], last_go["tp1"], last_go["tp2"]
                            if all(
                                x is not None and y is not None and abs(float(x) - float(y)) < 0.02
                                for x, y in [(e, le), (s, ls), (t1, lt1), (t2, lt2)]
                            ):
                                should_send = False
                    except (TypeError, ValueError, KeyError):
                        pass
        elif (
            status == DecisionStatus.no_go
            and blocked_by
            and settings.telegram_send_no_go_important
            and blocked_by.value in important_blocks
        ):
            # NO_GO important (ex: RR_TOO_LOW, SL_TOO_LARGE, NEWS_LOCK...)
            # -> on envoie tout de suite, puis on espace (cooldown dédié) pour éviter le spam.
            last_sent = get_last_telegram_sent_ts()
            if not last_sent:
                should_send = True
            else:
                try:
                    last_dt = datetime.fromisoformat(last_sent)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    now_dt = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=timezone.utc)
                    if now_dt - last_dt >= timedelta(minutes=settings.no_go_important_cooldown_minutes):
                        should_send = True
                except Exception:  # noqa: BLE001
                    # En cas de problème de parsing, on ne bloque pas l'envoi
                    should_send = True
        elif status == DecisionStatus.no_go and settings.telegram_send_no_go_important:
            last_sent = get_last_telegram_sent_ts()
            if not last_sent:
                should_send = True
                heartbeat_triggered = True
            else:
                last_dt = datetime.fromisoformat(last_sent)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                now_dt = datetime.fromisoformat(now_utc_str)
                if now_dt.tzinfo is None:
                    now_dt = now_dt.replace(tzinfo=timezone.utc)
                if now_dt - last_dt >= timedelta(minutes=settings.cooldown_minutes):
                    should_send = True
                    heartbeat_triggered = True
    if should_send and blocked_by == BlockedBy.duplicate_signal:
        should_send = False
    if should_send and was_telegram_sent(signal_key):
        should_send = False
    if (
        should_send
        and blocked_by == BlockedBy.data_off
        and was_alert_sent(f"data_off:{day_paris}:{now_utc_str[:13]}")
    ):
        should_send = False

    raw_message = formatter.format_message(
        symbol=symbol,
        decision=decision,
        entry=packet.proposed_entry,
        sl=packet.sl,
        tp1=packet.tp1,
        tp2=packet.tp2,
        direction=packet.state.get("setup_direction", "BUY"),
        current_price=current_price,
        market_provider=settings.market_provider,
        score_reasons=packet.reasons_rules,
    )
    message = raw_message
    # Coach AI uniquement si on va envoyer (économie d'API)
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
                ai_model = coach_output.model
                ai_input_tokens += coach_output.input_tokens
                ai_output_tokens += coach_output.output_tokens
                ai_cost_usd += coach_output.cost_usd
                ai_latency_ms = coach_output.latency_ms
                ai_output = {
                    "telegram_text": coach_output.telegram_text,
                    "coach_bullets": coach_output.coach_bullets,
                    "risk_note": coach_output.risk_note,
                }
                add_ai_usage(
                    date,
                    coach_output.input_tokens,
                    coach_output.output_tokens,
                    coach_output.cost_usd,
                    coach_output.cost_eur,
                )
                insert_ai_message(
                    now_utc_str,
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

    telegram_sent = 0
    telegram_error = None
    telegram_latency_ms = None
    sender = TelegramSender()

    prealert_text = None
    alert_key = None
    if blocked_by == BlockedBy.data_off and should_send:
        alert_key = f"data_off:{day_paris}:{now_utc_str[:13]}"
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
                            now_utc_str,
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
        if telegram_sent and blocked_by == BlockedBy.data_off:
            set_data_off_alert_sent(day_paris)
        if telegram_sent and status == DecisionStatus.go:
            set_active_trade(
                day_paris,
                packet.proposed_entry or 0,
                packet.sl or 0,
                packet.tp1 or 0,
                packet.tp2 or 0,
                packet.state.get("setup_direction", "BUY"),
                started_ts=packet.timestamps["ts_utc"],
            )
    if prealert_text and settings.telegram_enabled:
        sender.send_message(prealert_text)

    insert_signal(
        {
            "ts_utc": now_utc_str,
            "symbol": symbol,
            "tf_signal": settings.tf_signal,
            "tf_context": settings.tf_context,
            "status": decision.status.value,
            "blocked_by": decision.blocked_by.value if decision.blocked_by else None,
            "direction": packet.state.get("setup_direction", "BUY"),
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
    if telegram_sent:
        update_on_decision(day_paris, signal_key, now_utc_str)

    # Résumé du jour (une fois par jour en fin de session)
    try:
        now_paris = now_utc.astimezone(ZoneInfo("Europe/Paris")) if now_utc.tzinfo else datetime.fromisoformat(now_utc_str).replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Paris"))
        if settings.telegram_enabled and now_paris.hour >= settings.daily_summary_hour_paris:
            outcomes = get_trade_outcomes_today(day_paris)
            if outcomes and not was_daily_summary_sent(day_paris):
                total = sum(outcomes)
                n = len(outcomes)
                details = ", ".join(f"{x:+.1f}" for x in outcomes)
                msg = f"📊 Résumé du jour — {n} trade(s)\n\n{details}\n\nTotal: {total:+.1f} point"
                TelegramSender().send_message(msg)
                set_daily_summary_sent(day_paris)
    except Exception:  # noqa: BLE001
        pass

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


@app.post("/admin/reset-active-trade")
def admin_reset_active_trade(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    silent: bool = False,
    outcome_pips: float | None = Query(default=None, description="Résultat en points (+5 gain, -6 perte). Si fourni, utilisé tel quel. Sinon calculé au prix actuel."),
) -> dict:
    """Force l'arrêt du trade en cours et de son suivi. silent=True : pas de message Telegram (ex: script de redémarrage).
    Quand silent=False : si outcome_pips fourni, l'utilise ; sinon calcule au prix actuel. Envoie le résultat sur Telegram."""
    settings = get_settings()
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    from app.infra.db import clear_all_active_trades
    now_utc = datetime.now(timezone.utc)
    day_paris = now_utc.astimezone(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    active = get_active_trade(day_paris)
    outcome_val: float | None = None
    if not silent and active and settings.telegram_enabled and settings.telegram_chat_id:
        entry = float(active["active_entry"])
        direction = (active.get("active_direction") or "BUY").upper()
        if outcome_pips is not None:
            outcome_val = round(float(outcome_pips), 1)
        else:
            current_price = None
            try:
                provider = get_provider()
                if hasattr(provider, "get_tick"):
                    tick = provider.get_tick(settings.symbol_default)
                    if tick:
                        current_price = float(tick[0])
            except Exception:  # noqa: BLE001
                pass
            if current_price is not None:
                if direction == "BUY":
                    outcome_val = round(current_price - entry, 1)
                else:
                    outcome_val = round(entry - current_price, 1)
        if outcome_val is not None:
            record_trade_outcome(day_paris, outcome_val)
            clear_active_trade(day_paris, closed_ts=now_utc.isoformat())
            if outcome_pips >= 0:
                msg = (
                    f"✅ Trade clôturé\n\n"
                    f"Résultat du trade : PROFIT +{outcome_pips:.1f} point\n\n"
                    f"Suivi arrêté. Tu peux enchaîner sur un autre trade."
                )
            else:
                msg = (
                    f"✅ Trade clôturé\n\n"
                    f"Résultat du trade : PERTE {outcome_pips:.1f} point\n\n"
                    f"Suivi arrêté. Tu peux enchaîner sur un autre trade."
                )
            try:
                TelegramSender().send_message(msg)
            except Exception:  # noqa: BLE001
                pass
            outcome_pips = outcome_val  # pour le return
    if outcome_val is None and outcome_pips is None:
        n = clear_all_active_trades()
        if not silent and settings.telegram_enabled and settings.telegram_chat_id and not active:
            msg = (
                "🟢 Aucun trade en cours\n\n"
                "Suivi prêt pour les prochains trades."
            )
            try:
                TelegramSender().send_message(msg)
            except Exception:  # noqa: BLE001
                pass
        elif not silent and settings.telegram_enabled and settings.telegram_chat_id and active:
            msg = (
                "🟢 Trade clôturé (prix indisponible)\n\n"
                "Suivi arrêté. Le système reprend l'analyse."
            )
            try:
                TelegramSender().send_message(msg)
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "rows_cleared": n, "message": "Trade effacé. Suivi prêt pour les prochains trades.", "outcome_pips": None}
    return {"ok": True, "rows_cleared": 1, "message": "Trade clôturé, résultat envoyé sur Telegram.", "outcome_pips": outcome_val}


@app.post("/trade/manual-close")
def trade_manual_close(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    outcome_pips: float | None = Query(default=None, description="Résultat en points (+5 gain, -6 perte). Si fourni, utilisé tel quel. Sinon calculé au prix actuel."),
) -> dict:
    """
    À appeler quand tu as fermé le trade manuellement (ex. sur MT5).
    - Si outcome_pips fourni (ex. ?outcome_pips=5 ou ?outcome_pips=-6) : utilise cette valeur.
    - Sinon : calcule au prix actuel MT5.
    Enregistre le résultat, efface le trade actif et envoie le message sur Telegram.
    """
    settings = get_settings()
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    now_utc = datetime.now(timezone.utc)
    day_paris = now_utc.astimezone(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    active = get_active_trade(day_paris)
    if not active:
        return {"ok": True, "message": "Aucun trade en cours.", "outcome_pips": None}
    entry = float(active["active_entry"])
    direction = (active.get("active_direction") or "BUY").upper()
    pnl_pips: float | None = None
    if outcome_pips is not None:
        pnl_pips = round(float(outcome_pips), 1)
    else:
        current_price = None
        try:
            provider = get_provider()
            if hasattr(provider, "get_tick"):
                tick = provider.get_tick(settings.symbol_default)
                if tick:
                    current_price = float(tick[0])
        except Exception:  # noqa: BLE001
            pass
        if current_price is None:
            return {
                "ok": False,
                "message": "Prix actuel indisponible (vérifier le bridge MT5). Indique outcome_pips pour forcer le résultat.",
                "outcome_pips": None,
            }
        if direction == "BUY":
            pnl_pips = round(current_price - entry, 1)
        else:
            pnl_pips = round(entry - current_price, 1)
    record_trade_outcome(day_paris, pnl_pips)
    clear_active_trade(day_paris, closed_ts=now_utc.isoformat())
    if settings.telegram_enabled and settings.telegram_chat_id:
        if pnl_pips >= 0:
            result_msg = (
                f"✅ Trade clôturé manuellement\n\n"
                f"Résultat du trade : PROFIT +{pnl_pips:.1f} point\n\n"
                f"Tu peux enchaîner sur un autre trade."
            )
        else:
            result_msg = (
                f"✅ Trade clôturé manuellement\n\n"
                f"Résultat du trade : PERTE {pnl_pips:.1f} point\n\n"
                f"Tu peux enchaîner sur un autre trade."
            )
        try:
            TelegramSender().send_message(result_msg)
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "message": "Trade clôturé, résultat envoyé sur Telegram.", "outcome_pips": pnl_pips}


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


@app.get("/stats/summary")
def stats_summary(
    date: str | None = None,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    """
    Résumé du jour : nombre de GO/NO_GO, outcomes (points), budget perte.
    Paramètre optionnel date (YYYY-MM-DD, défaut = aujourd'hui Paris).
    """
    if date:
        day_paris = date
    else:
        day_paris = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    return get_stats_summary(day_paris)


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
    elif score_total < settings.go_min_score:
        status = DecisionStatus.no_go
        blocked_by = BlockedBy.no_setup
        why = ["Score insuffisant"]

    decision = DecisionResult(
        status=status,
        blocked_by=blocked_by,
        score_total=score_total,
        score_effective=0 if status == DecisionStatus.no_go and blocked_by else score_total,
        confidence=min(100, max(50, score_total)),
        quality=Quality.a_plus if score_total >= settings.a_plus_min_score else Quality.a if score_total >= settings.go_min_score else Quality.b,
        why=why,
    )

    cp_preview = None
    if hasattr(provider, "get_tick"):
        tick = provider.get_tick(symbol)
        if tick:
            cp_preview = float(tick[0])
    raw_message = formatter.format_message(
        symbol=symbol,
        decision=decision,
        entry=packet.proposed_entry,
        sl=packet.sl,
        tp1=packet.tp1,
        tp2=packet.tp2,
        direction=packet.state.get("setup_direction", "BUY"),
        current_price=cp_preview,
        market_provider=settings.market_provider,
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
                    packet.timestamps["ts_utc"],
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
