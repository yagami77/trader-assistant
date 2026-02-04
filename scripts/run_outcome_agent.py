from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env.local", override=True)

sys.path.insert(0, str(REPO_ROOT))

from app.config import get_settings
from app.providers.remote_mt5_provider import RemoteMT5Provider
from app.infra.db import get_conn, init_db, upsert_signal_outcome
from app.agents.signal_outcome_agent import evaluate_outcome, OutcomeResult

LOG_PATH = REPO_ROOT / "logs" / "outcome_agent.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger("outcome_agent")


TF_MINUTES = {
    "M1": 1,
    "M2": 2,
    "M3": 3,
    "M4": 4,
    "M5": 5,
    "M10": 10,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H2": 120,
    "H4": 240,
}


def _parse_ts(value: object) -> datetime:
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError("Invalid timestamp")


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Invalid HH:MM")
    return int(parts[0]), int(parts[1])


def _is_in_market_close_window(now_utc: datetime, start_hhmm: str, end_hhmm: str) -> bool:
    paris = ZoneInfo("Europe/Paris")
    now = now_utc.astimezone(paris)
    start_h, start_m = _parse_hhmm(start_hhmm)
    end_h, end_m = _parse_hhmm(end_hhmm)
    start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _fetch_candidates(conn: sqlite3.Connection, lookback_hours: int, max_rows: int) -> List[Dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    rows = conn.execute(
        """
        SELECT s.id, s.ts_utc, s.symbol, s.direction, s.entry, s.sl, s.tp1, s.tp2, s.decision_packet_json
        FROM signals s
        LEFT JOIN signal_outcomes o ON o.signal_id = s.id
        WHERE o.signal_id IS NULL
          AND s.ts_utc >= ?
        ORDER BY s.ts_utc ASC
        LIMIT ?
        """,
        (since.isoformat(), max_rows),
    ).fetchall()
    return [dict(row) for row in rows]


def main() -> None:
    settings = get_settings()
    if not settings.outcome_agent_enabled:
        logger.info("Outcome agent disabled via env. Exiting.")
        return

    init_db()
    provider = RemoteMT5Provider()
    tf = settings.outcome_agent_candle_tf.upper()
    tf_minutes = TF_MINUTES.get(tf, 1)
    interval = settings.outcome_agent_interval_sec
    min_age_hours = settings.outcome_agent_min_age_hours
    run_only_during_market_close = settings.outcome_agent_run_only_during_market_close
    market_close_start = settings.market_close_start
    market_close_end = settings.market_close_end
    horizon_minutes = settings.outcome_agent_horizon_minutes
    lookback = settings.outcome_agent_lookback_hours
    max_per_loop = settings.outcome_agent_max_per_loop

    logger.info(
        "Outcome agent started: tf=%s, horizon=%dm, interval=%ds, max/loop=%d, min_age=%dh, run_in_close_only=%s",
        tf,
        horizon_minutes,
        interval,
        max_per_loop,
        min_age_hours,
        run_only_during_market_close,
    )

    min_age_seconds = min_age_hours * 3600

    while True:
        try:
            now = datetime.now(timezone.utc)
            if run_only_during_market_close and not _is_in_market_close_window(
                now, market_close_start, market_close_end
            ):
                logger.info("Hors fenêtre marché fermé (Paris %s–%s), prochaine vérif dans %ds", market_close_start, market_close_end, interval)
                time.sleep(interval)
                continue

            conn = get_conn()
            candidates = _fetch_candidates(conn, lookback, max_per_loop)
            for row in candidates:
                try:
                    signal_ts = _parse_ts(row["ts_utc"])
                    if (now - signal_ts).total_seconds() < min_age_seconds:
                        continue

                    direction = (row.get("direction") or "BUY").upper()
                    entry = float(row.get("entry") or 0.0)
                    sl = float(row.get("sl") or 0.0)
                    tp1 = float(row.get("tp1") or 0.0)
                    tp2 = float(row.get("tp2") or 0.0)

                    tick_size = 0.01
                    if row.get("decision_packet_json"):
                        try:
                            pkt = json.loads(row["decision_packet_json"])
                            tick_size = float(pkt.get("tick_size") or tick_size)
                        except Exception:
                            pass

                    count = max(1, int(horizon_minutes / tf_minutes))
                    try:
                        candles = provider.get_candles(row["symbol"], tf, count)
                    except Exception as exc:
                        result = OutcomeResult(
                            outcome_status="UNKNOWN",
                            outcome_reason=f"MT5 bridge error: {exc}",
                            hit_tp1=0,
                            hit_tp2=0,
                            hit_sl=0,
                            max_favorable_points=None,
                            max_adverse_points=None,
                            pnl_points=None,
                            price_path_start_ts=None,
                            price_path_end_ts=None,
                        )
                    else:
                        # filter candles within horizon
                        end_ts = signal_ts + timedelta(minutes=horizon_minutes)
                        filtered = []
                        for c in candles:
                            ts = c.get("ts") or c.get("time_msc") or c.get("time")
                            dt = _parse_ts(ts) if ts else None
                            if dt and signal_ts <= dt <= end_ts:
                                filtered.append(c)

                        result = evaluate_outcome(
                            filtered,
                            direction=direction,
                            entry=entry,
                            sl=sl,
                            tp1=tp1,
                            tp2=tp2,
                            tick_size=tick_size,
                        )
                    outcome_payload = {
                        "signal_id": row["id"],
                        "ts_checked_utc": datetime.now(timezone.utc).isoformat(),
                        "outcome_status": result.outcome_status,
                        "outcome_reason": result.outcome_reason,
                        "hit_tp1": result.hit_tp1,
                        "hit_tp2": result.hit_tp2,
                        "hit_sl": result.hit_sl,
                        "max_favorable_points": result.max_favorable_points,
                        "max_adverse_points": result.max_adverse_points,
                        "pnl_points": result.pnl_points,
                        "horizon_minutes": horizon_minutes,
                        "price_path_start_ts": result.price_path_start_ts,
                        "price_path_end_ts": result.price_path_end_ts,
                    }
                    upsert_signal_outcome(outcome_payload)
                except Exception as exc:
                    logger.warning("Outcome failed for signal %s: %s", row.get("id"), exc)
            conn.close()
        except Exception as exc:
            logger.warning("Loop error: %s", exc)
            time.sleep(60)
        time.sleep(interval)


if __name__ == "__main__":
    main()
