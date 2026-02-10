"""
Agent de fond : évalue les signaux passés (TP/SL touchés, PnL en pts).
S'exécute périodiquement (ex: nuit) sans impacter /analyze.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Charger .env.local
_REPO_ROOT = Path(__file__).resolve().parents[2]
_env_local = _REPO_ROOT / ".env.local"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local, override=True)
    except ImportError:
        pass

sys.path.insert(0, str(_REPO_ROOT))

import httpx
from app.config import get_settings
from app.infra.db import get_conn, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _fetch_candles_after(symbol: str, tf: str, ts_utc: str, count: int = 200) -> List[Dict[str, Any]]:
    """Récupère les bougies après ts_utc via le bridge MT5."""
    settings = get_settings()
    if not settings.mt5_bridge_url:
        return []
    url = settings.mt5_bridge_url.rstrip("/") + "/candles"
    try:
        resp = httpx.get(
            url,
            params={"symbol": symbol, "timeframe": tf, "count": str(count)},
            timeout=10.0,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        candles = data.get("candles", [])
        if not candles:
            return []
        # Filtrer les bougies après ts_utc
        out = []
        for c in candles:
            t = c.get("ts") or c.get("time") or c.get("time_msc")
            if t is None:
                continue
            if isinstance(t, (int, float)):
                ts_sec = float(t) / 1000.0 if t > 1e12 else float(t)
                from datetime import datetime, timezone
                candle_dt = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
            else:
                try:
                    candle_dt = __import__("datetime").datetime.fromisoformat(str(t).replace("Z", "+00:00"))
                except ValueError:
                    continue
            try:
                ref_dt = __import__("datetime").datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
            except ValueError:
                ref_dt = __import__("datetime").datetime.fromisoformat(ts_utc[:19].replace("Z", "+00:00"))
            if candle_dt.tzinfo is None:
                candle_dt = candle_dt.replace(tzinfo=timezone.utc)
            if ref_dt.tzinfo is None:
                ref_dt = ref_dt.replace(tzinfo=timezone.utc)
            if candle_dt >= ref_dt:
                out.append(c)
        return sorted(out, key=lambda c: float(c.get("ts", 0) or c.get("time", 0)))
    except Exception as e:
        log.warning("Bridge candles: %s", e)
        return []


def _check_outcome(
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    candles: List[Dict],
) -> tuple[str, Optional[float], Optional[str]]:
    """
    Détermine si SL, TP1 ou TP2 a été touché.
    Retourne (outcome, pnl_pts, outcome_ts_utc).
    """
    if not candles:
        return ("UNKNOWN", None, None)
    for c in candles:
        h = float(c.get("high", 0) or 0)
        l = float(c.get("low", 0) or 0)
        t = c.get("ts") or c.get("time") or c.get("time_msc")
        ts_str = None
        if isinstance(t, (int, float)):
            ts = float(t) / 1000.0 if t > 1e12 else float(t)
            from datetime import datetime, timezone
            ts_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        elif isinstance(t, str):
            ts_str = t

        if direction == "BUY":
            if l <= sl:
                return ("SL_HIT", entry - sl, ts_str)
            if h >= tp2:
                return ("TP2_HIT", tp2 - entry, ts_str)
            if h >= tp1:
                return ("TP1_HIT", tp1 - entry, ts_str)
        else:
            if h >= sl:
                return ("SL_HIT", sl - entry, ts_str)
            if l <= tp2:
                return ("TP2_HIT", entry - tp2, ts_str)
            if l <= tp1:
                return ("TP1_HIT", entry - tp1, ts_str)
    return ("OPEN", None, None)


def run_once(symbol: str = "XAUUSD", limit: int = 50) -> int:
    """Évalue les signaux GO récents non encore évalués."""
    init_db()
    conn = get_conn()
    # Signaux GO envoyés, pas encore dans signal_outcomes
    rows = conn.execute(
        """
        SELECT s.id, s.ts_utc, s.symbol, s.direction, s.entry, s.sl, s.tp1, s.tp2
        FROM signals s
        LEFT JOIN signal_outcomes o ON o.signal_id = s.id
        WHERE s.status = 'GO' AND s.telegram_sent = 1
          AND s.entry IS NOT NULL AND s.sl IS NOT NULL
          AND o.id IS NULL
        ORDER BY s.ts_utc DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    settings = get_settings()
    tf = getattr(settings, "tf_signal", "M15") or "M15"
    evaluated = 0
    for row in rows:
        signal_id = row["id"]
        ts_utc = row["ts_utc"]
        sym = row["symbol"] or symbol
        direction = row["direction"] or "BUY"
        entry = float(row["entry"] or 0)
        sl = float(row["sl"] or 0)
        tp1 = float(row["tp1"] or 0)
        tp2 = float(row["tp2"] or 0)
        if entry <= 0 or sl <= 0:
            continue
        candles = _fetch_candles_after(sym, tf, ts_utc, 200)
        outcome, pnl_pts, outcome_ts = _check_outcome(direction, entry, sl, tp1, tp2, candles)
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO signal_outcomes (signal_id, ts_utc, symbol, direction, entry, sl, tp1, tp2, outcome, pnl_pts, outcome_ts_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (signal_id, ts_utc, sym, direction, entry, sl, tp1, tp2, outcome, pnl_pts, outcome_ts),
        )
        conn.commit()
        conn.close()
        evaluated += 1
        log.info("Signal %s: %s (PnL=%s pts)", ts_utc[:19], outcome, pnl_pts)
    return evaluated


def main() -> None:
    parser = argparse.ArgumentParser(description="Signal Outcome Agent - évalue les signaux passés")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbole")
    parser.add_argument("--limit", type=int, default=50, help="Nombre max de signaux à traiter")
    parser.add_argument("--once", action="store_true", help="Exécution unique (pas de boucle)")
    parser.add_argument("--interval", type=int, default=86400, help="Intervalle en secondes (défaut: 24h)")
    args = parser.parse_args()

    if args.once:
        n = run_once(args.symbol, args.limit)
        log.info("Évalué %d signaux", n)
        return

    import time
    while True:
        try:
            n = run_once(args.symbol, args.limit)
            if n > 0:
                log.info("Évalué %d signaux", n)
        except Exception as e:
            log.exception("Erreur: %s", e)
        log.info("Prochaine exécution dans %ds", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
