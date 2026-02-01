from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models import Bias, DecisionPacket
from app.agents.context_agent import get_context_summary
from app.agents.news_agent import get_lock
from app.agents.news_impact_agent import build_news_impact_summary
from app.engines.news_timing import compute_news_timing
from app.engines.setup_engine import detect_setups


SESSION_WINDOWS = [
    ((14, 30), (18, 30)),
    ((20, 0), (22, 0)),
]


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("Invalid HH:MM")
    return int(parts[0]), int(parts[1])


def _is_in_market_close(now_paris: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    start_h, start_m = _parse_hhmm(start_hhmm)
    end_h, end_m = _parse_hhmm(end_hhmm)
    start = now_paris.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now_paris.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if start <= end:
        return start <= now_paris <= end
    return now_paris >= start or now_paris <= end


def _is_in_session(now_paris: datetime, mode: str, close_start: str, close_end: str) -> bool:
    if mode == "off":
        return True
    if mode == "market_close":
        return not _is_in_market_close(now_paris, close_start, close_end)
    for (start_h, start_m), (end_h, end_m) in SESSION_WINDOWS:
        start = now_paris.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = now_paris.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        if start <= now_paris <= end:
            return True
    return False


def _parse_timestamp(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            try:
                ts = float(raw)
                if ts > 1_000_000_000_000:
                    return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except ValueError:
                return None
    return None


def build_decision_packet(provider, symbol: str) -> DecisionPacket:
    settings = get_settings()
    now_utc = provider.get_server_time()
    now_paris = now_utc.astimezone(ZoneInfo("Europe/Paris"))

    session_ok = settings.always_in_session or _is_in_session(
        now_paris,
        settings.trading_session_mode,
        settings.market_close_start,
        settings.market_close_end,
    )
    spread = provider.get_spread(symbol)
    atr = 1.1
    bias = Bias.up
    candles = provider.get_candles(symbol, settings.tf_signal, 50)
    setup = detect_setups(candles)
    news_lock, next_event, provider_ok, raw_count, lock_window = get_lock(
        now_utc,
        settings.news_lock_high_pre_min,
        settings.news_lock_high_post_min,
        settings.news_lock_med_pre_min,
        settings.news_lock_med_post_min,
    )
    news_timing = compute_news_timing(
        now_utc,
        next_event,
        settings.news_lock_high_pre_min,
        settings.news_lock_high_post_min,
        settings.news_lock_med_pre_min,
        settings.news_lock_med_post_min,
        settings.news_prealert_minutes,
    )
    news_lock = news_timing.lock_active
    news_impact_summary = build_news_impact_summary(next_event)
    context_summary, context_sources = get_context_summary()
    sources_used = [
        f"news:{settings.news_provider.lower()}",
        f"market:{settings.market_provider.lower()}",
    ] + context_sources
    if not provider_ok:
        sources_used.append("NEWS_PROVIDER_DOWN")

    entry = setup.entry
    sl = setup.sl
    tp1 = setup.tp1
    tp2 = setup.tp2
    rr_tp2 = setup.rr_tp2

    data_latency_ms = 9999
    if candles:
        last = candles[-1]
        last_ts = _parse_timestamp(last.get("ts") or last.get("time_msc") or last.get("time"))
        if last_ts:
            data_latency_ms = int((now_utc - last_ts).total_seconds() * 1000)
            if data_latency_ms < 0:
                data_latency_ms = 0

    return DecisionPacket(
        session_ok=session_ok,
        news_lock=news_lock,
        news_next_event=(
            {
                "datetime_iso": next_event.datetime_iso,
                "impact": next_event.impact,
                "title": next_event.title,
            }
            if next_event
            else None
        ),
        news_next_event_details=(
            {
                "datetime_iso": next_event.datetime_iso,
                "impact": next_event.impact,
                "title": next_event.title,
                "currency": next_event.currency,
                "country": next_event.country,
                "actual": next_event.actual,
                "forecast": next_event.forecast,
                "previous": next_event.previous,
            }
            if next_event
            else None
        ),
        spread=spread,
        news_impact_summary=news_impact_summary,
        spread_max=settings.spread_max,
        atr=atr,
        atr_max=settings.atr_max,
        bias_h1=bias,
        setups_detected=setup.setups,
        proposed_entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        rr_tp2=rr_tp2,
        rr_min=settings.rr_min,
        score_rules=0,
        reasons_rules=[],
        sources_used=sources_used,
        context_summary=context_summary,
        news_state={
            "minutes_to_event": news_timing.minutes_to_event,
            "moment": news_timing.moment_label,
            "horizon_minutes": news_timing.horizon_minutes,
            "lock_active": news_timing.lock_active,
            "lock_reason": news_timing.lock_reason,
            "lock_window_start_min": news_timing.lock_window_start_min,
            "lock_window_end_min": news_timing.lock_window_end_min,
            "provider_ok": provider_ok,
            "raw_count": raw_count,
            "should_pre_alert": news_timing.should_pre_alert,
            "bucket_label": news_timing.bucket_label,
            "next_event": (
                {
                    "datetime_iso": next_event.datetime_iso,
                    "impact": next_event.impact,
                    "title": next_event.title,
                }
                if next_event
                else None
            ),
        },
        state={
            "daily_budget_used": 0.0,
            "cooldown_ok": True,
        },
        timestamps={
            "ts_utc": now_utc.isoformat(),
            "ts_paris": now_paris.isoformat(),
        },
        data_latency_ms=data_latency_ms,
    )


def build_fallback_packet(symbol: str, now_utc: Optional[datetime] = None) -> DecisionPacket:
    settings = get_settings()
    safe_now = now_utc or datetime.now(timezone.utc)
    now_paris = safe_now.astimezone(ZoneInfo("Europe/Paris"))
    session_ok = settings.always_in_session or _is_in_session(
        now_paris,
        settings.trading_session_mode,
        settings.market_close_start,
        settings.market_close_end,
    )
    return DecisionPacket(
        session_ok=session_ok,
        news_lock=False,
        news_next_event=None,
        news_impact_summary=[],
        news_next_event_details=None,
        news_state={},
        spread=settings.spread_max + 1.0,
        spread_max=settings.spread_max,
        atr=settings.atr_max + 1.0,
        atr_max=settings.atr_max,
        bias_h1=Bias.range,
        setups_detected=[],
        proposed_entry=0.0,
        sl=0.0,
        tp1=0.0,
        tp2=0.0,
        rr_tp2=0.0,
        rr_min=settings.rr_min,
        score_rules=0,
        reasons_rules=[],
        sources_used=[],
        context_summary=[],
        state={
            "daily_budget_used": 0.0,
            "cooldown_ok": True,
        },
        timestamps={
            "ts_utc": safe_now.isoformat(),
            "ts_paris": now_paris.isoformat(),
        },
        data_latency_ms=9999,
    )
