from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import get_settings
from app.infra.db import get_conn


def _get(row, key: str, default):
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, IndexError, TypeError):
        return default


@dataclass(frozen=True)
class StateRow:
    day_paris: str
    daily_loss_amount: float
    daily_budget_amount: float
    last_signal_key: Optional[str]
    last_ts: Optional[str]
    consecutive_losses: int
    last_setup_direction: Optional[str]
    last_setup_entry: Optional[float]
    last_setup_bar_ts: Optional[str]
    setup_confirm_count: int
    trade_state_machine: Optional[str] = None
    last_breakout_level: Optional[float] = None
    market_phase: Optional[str] = None
    last_trade_closed_ts: Optional[str] = None


def _row_to_state(row) -> StateRow:
    return StateRow(
        day_paris=row["day_paris"],
        daily_loss_amount=float(_get(row, "daily_loss_amount", 0.0)),
        daily_budget_amount=float(_get(row, "daily_budget_amount", 20.0)),
        last_signal_key=_get(row, "last_signal_key", None),
        last_ts=_get(row, "last_ts", None),
        consecutive_losses=int(_get(row, "consecutive_losses", 0)),
        last_setup_direction=_get(row, "last_setup_direction", None),
        last_setup_entry=float(v) if (v := _get(row, "last_setup_entry", None)) is not None else None,
        last_setup_bar_ts=_get(row, "last_setup_bar_ts", None),
        setup_confirm_count=int(_get(row, "setup_confirm_count", 0)),
        trade_state_machine=_get(row, "trade_state_machine", None),
        last_breakout_level=float(v) if (v := _get(row, "last_breakout_level", None)) is not None else None,
        market_phase=_get(row, "market_phase", None),
        last_trade_closed_ts=_get(row, "last_trade_closed_ts", None),
    )


def get_today_state(day_paris: str) -> StateRow:
    settings = get_settings()
    conn = get_conn()
    row = conn.execute("SELECT * FROM state WHERE day_paris = ?", (day_paris,)).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO state (
                day_paris, daily_loss_amount, daily_budget_amount,
                last_signal_key, last_ts, consecutive_losses,
                last_setup_direction, last_setup_entry, last_setup_bar_ts, setup_confirm_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (day_paris, 0.0, settings.daily_budget_amount, None, None, 0, None, None, None, 0),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM state WHERE day_paris = ?", (day_paris,)).fetchone()
    conn.close()
    return _row_to_state(row)


def update_on_decision(day_paris: str, signal_key: str, ts_utc: str) -> None:
    conn = get_conn()
    conn.execute(
        """
        UPDATE state
        SET last_signal_key = ?, last_ts = ?
        WHERE day_paris = ?
        """,
        (signal_key, ts_utc, day_paris),
    )
    conn.commit()
    conn.close()


def is_budget_reached(state: StateRow) -> bool:
    return state.daily_loss_amount >= state.daily_budget_amount


def is_cooldown_ok(state: StateRow, now_utc: datetime) -> bool:
    if not state.last_ts:
        return True
    last_ts = datetime.fromisoformat(state.last_ts)
    # Si last_ts est naïf (sans timezone), le traiter comme UTC
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    cooldown = timedelta(minutes=get_settings().cooldown_minutes)
    return now_utc - last_ts >= cooldown


def update_setup_context(
    day_paris: str,
    direction: str,
    entry: float,
    bar_ts: Optional[str],
    confirm_count: int,
) -> None:
    conn = get_conn()
    conn.execute(
        """
        UPDATE state SET
            last_setup_direction = ?,
            last_setup_entry = ?,
            last_setup_bar_ts = ?,
            setup_confirm_count = ?
        WHERE day_paris = ?
        """,
        (direction, entry, bar_ts, confirm_count, day_paris),
    )
    conn.commit()
    conn.close()


def update_smart_context(
    day_paris: str,
    trade_state_machine: Optional[str] = None,
    last_structure_type: Optional[str] = None,
    last_breakout_level: Optional[float] = None,
    last_pullback_zone_lo: Optional[float] = None,
    last_pullback_zone_hi: Optional[float] = None,
    market_phase: Optional[str] = None,
    market_phase_since_ts: Optional[str] = None,
    trade_state_since_ts: Optional[str] = None,
) -> None:
    """Met à jour le contexte intelligent (state machine, phase marché)."""
    conn = get_conn()
    conn.execute(
        """
        UPDATE state SET
            trade_state_machine = COALESCE(?, trade_state_machine),
            last_structure_type = COALESCE(?, last_structure_type),
            last_breakout_level = COALESCE(?, last_breakout_level),
            last_pullback_zone_lo = COALESCE(?, last_pullback_zone_lo),
            last_pullback_zone_hi = COALESCE(?, last_pullback_zone_hi),
            market_phase = COALESCE(?, market_phase),
            market_phase_since_ts = COALESCE(?, market_phase_since_ts),
            trade_state_since_ts = COALESCE(?, trade_state_since_ts)
        WHERE day_paris = ?
        """,
        (
            trade_state_machine,
            last_structure_type,
            last_breakout_level,
            last_pullback_zone_lo,
            last_pullback_zone_hi,
            market_phase,
            market_phase_since_ts,
            trade_state_since_ts,
            day_paris,
        ),
    )
    conn.commit()
    conn.close()


def get_effective_cooldown_minutes(
    state: StateRow,
    market_phase: Optional[str],
    now_utc: datetime,
) -> int:
    """
    Cooldown effectif : base + additionnel si CONSOLIDATION (quand cooldown_dynamic_enabled).
    """
    settings = get_settings()
    base = settings.cooldown_after_trade_minutes
    if not getattr(settings, "cooldown_dynamic_enabled", False):
        return base
    if market_phase == "CONSOLIDATION" and state.last_trade_closed_ts:
        try:
            closed_dt = datetime.fromisoformat(state.last_trade_closed_ts)
            if closed_dt.tzinfo is None:
                closed_dt = closed_dt.replace(tzinfo=timezone.utc)
            if now_utc.tzinfo is None:
                now_utc = now_utc.replace(tzinfo=timezone.utc)
            elapsed = (now_utc - closed_dt).total_seconds() / 60
            extra = getattr(settings, "cooldown_consolidation_minutes", 15)
            if elapsed < base + extra:
                return base + extra
        except (ValueError, TypeError):
            pass
    return base
