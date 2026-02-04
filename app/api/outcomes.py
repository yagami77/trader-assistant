from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.infra.db import get_conn

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@router.get("/latest")
def outcomes_latest(
    limit: int = 50,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> list[dict]:
    settings = get_settings()
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    limit = max(1, min(limit, 200))
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT
            s.id as signal_id,
            s.ts_utc,
            s.symbol,
            s.status,
            s.blocked_by,
            s.entry,
            s.sl,
            s.tp1,
            s.tp2,
            o.outcome_status,
            o.outcome_reason,
            o.hit_tp1,
            o.hit_tp2,
            o.hit_sl,
            o.max_favorable_points,
            o.max_adverse_points,
            o.pnl_points,
            o.ts_checked_utc
        FROM signals s
        LEFT JOIN signal_outcomes o ON o.signal_id = s.id
        ORDER BY s.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
