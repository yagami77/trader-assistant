#!/usr/bin/env python
"""Boucle infinie: appelle run_once toutes les N secondes."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ajouter le repo root au path
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from app.scripts.run_once import run_once

# Logging vers runner.log
LOG_PATH = _REPO_ROOT / "logs" / "runner.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("runner_loop")


def main() -> None:
    parser = argparse.ArgumentParser(description="Runner loop - call /analyze every N seconds")
    parser.add_argument("--interval", type=int, default=300, help="Interval in seconds (default: 300)")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol")
    parser.add_argument("--timeframe", default="M15", help="Timeframe")
    args = parser.parse_args()

    # Écrire interval_sec dans runner_state pour next_run_eta_sec
    state_path = _REPO_ROOT / "data" / "runner_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if state_path.exists():
        try:
            existing = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["interval_sec"] = args.interval
    state_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    logger.info("Runner loop started, interval=%ds", args.interval)
    while True:
        try:
            code = run_once(symbol=args.symbol, timeframe=args.timeframe)
            if code != 0:
                logger.warning("run_once exited with code %d", code)
            else:
                logger.info("run_once OK")
        except Exception as e:
            logger.exception("run_once failed: %s", e)
            for attempt in range(2):  # 2 retries = 3 total attempts
                time.sleep(5)
                try:
                    code = run_once(symbol=args.symbol, timeframe=args.timeframe)
                    if code == 0:
                        break
                except Exception as retry_e:
                    logger.exception("Retry %d failed: %s", attempt + 1, retry_e)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
