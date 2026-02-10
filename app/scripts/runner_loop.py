"""Boucle d'appel périodique à /analyze pour envoyer les signaux Telegram."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import httpx

# Charger .env.local si présent
_REPO_ROOT = Path(__file__).resolve().parents[2]
_env_local = _REPO_ROOT / ".env.local"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local)
    except ImportError:
        pass

API_URL_DEFAULT = os.environ.get("API_URL", "http://127.0.0.1:8081")
TIMEOUT_SEC = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(description="Runner loop - appelle /analyze périodiquement")
    parser.add_argument("--interval", type=int, default=60, help="Intervalle en secondes entre chaque appel")
    parser.add_argument("--symbol", type=str, default="XAUUSD", help="Symbole à analyser")
    parser.add_argument("--timeframe", type=str, default="M15", help="Timeframe (non utilisé par l'API)")
    args = parser.parse_args()

    url = API_URL_DEFAULT.rstrip("/") + "/analyze"
    log.info("Runner démarré: %s toutes les %ds (symbol=%s)", url, args.interval, args.symbol)

    while True:
        try:
            resp = httpx.post(
                url,
                json={"symbol": args.symbol},
                timeout=TIMEOUT_SEC,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("decision", {}).get("status", "?")
            blocked = data.get("decision", {}).get("blocked_by", "")
            log.info("Analyze OK: status=%s blocked_by=%s", status, blocked or "-")
        except httpx.ConnectError as e:
            log.warning("API injoignable: %s", e)
        except httpx.HTTPStatusError as e:
            log.warning("HTTP %s: %s", e.response.status_code, e)
        except Exception as e:
            log.exception("Erreur: %s", e)

        if args.once:
            log.info("Mode --once : arrêt après un analyse")
            sys.exit(0)

        try:
            import time
            time.sleep(args.interval)
        except KeyboardInterrupt:
            log.info("Arrêt demandé")
            sys.exit(0)


if __name__ == "__main__":
    main()
