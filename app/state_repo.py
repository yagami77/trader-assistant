from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.config import get_settings
from app.infra.db import get_conn


@dataclass(frozen=True)
class StateRow:
    day_paris: str
    daily_loss_amount: float
    daily_budget_amount: float
    last_signal_key: Optional[str]
    last_ts: Optional[str]
    consecutive_losses: int


def _row_to_state(row) -> StateRow:
    return StateRow(
        day_paris=row["day_paris"],
        daily_loss_amount=row["daily_loss_amount"],
        daily_budget_amount=row["daily_budget_amount"],
        last_signal_key=row["last_signal_key"],
        last_ts=row["last_ts"],
        consecutive_losses=row["consecutive_losses"],
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
                last_signal_key, last_ts, consecutive_losses
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (day_paris, 0.0, settings.daily_budget_amount, None, None, 0),
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
    cooldown = timedelta(minutes=get_settings().cooldown_minutes)
    return now_utc - last_ts >= cooldown
