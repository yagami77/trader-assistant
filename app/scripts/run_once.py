#!/usr/bin/env python
"""Appelle /analyze une fois. Lit .env.local via dotenv."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Charger .env.local avant toute import de app
_REPO_ROOT = Path(__file__).resolve().parents[2]
_env_local = _REPO_ROOT / ".env.local"
if _env_local.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_local, override=True)

import httpx


def _load_admin_token() -> str:
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        # Fallback: lire directement .env.local
        if _env_local.exists():
            for line in _env_local.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("ADMIN_TOKEN=") and "=" in line:
                    return line.split("=", 1)[1].strip().strip('"\'')
    return token


def run_once(symbol: str = "XAUUSD", timeframe: str = "M15", url: str = "http://127.0.0.1:8081/analyze") -> int:
    token = _load_admin_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Admin-Token"] = token

    payload = {"symbol": symbol, "timeframe": timeframe}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        decision = data.get("decision", {})
        status_val = decision.get("status", "UNKNOWN")
        blocked_by = decision.get("blocked_by")
        score = decision.get("score_total")

        ts = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        log_line = f"{ts} | http={resp.status_code} | status={status_val} | blocked_by={blocked_by} | score={score}"
        print(log_line)

        # Écrire l'état pour /runner/status
        state_path = _REPO_ROOT / "data" / "runner_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if state_path.exists():
            try:
                existing = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        state = {
            **existing,
            "last_run_utc": ts,
            "last_http_status": resp.status_code,
            "last_decision_status": status_val,
            "last_blocked_by": blocked_by,
            "last_score_total": score,
            "last_error": None if resp.is_success else (data.get("detail") or resp.text[:200]),
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        return 0 if resp.is_success else 1
    except Exception as e:
        ts = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        print(f"{ts} | ERROR | {e}")
        state_path = _REPO_ROOT / "data" / "runner_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        if state_path.exists():
            try:
                existing = json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        state = {
            **existing,
            "last_run_utc": ts,
            "last_http_status": None,
            "last_decision_status": None,
            "last_blocked_by": None,
            "last_score_total": None,
            "last_error": str(e),
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run /analyze once")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol (default: XAUUSD)")
    parser.add_argument("--timeframe", default="M15", help="Timeframe (default: M15)")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8081/analyze",
        help="Analyze endpoint URL",
    )
    args = parser.parse_args()
    return run_once(symbol=args.symbol, timeframe=args.timeframe, url=args.url)


if __name__ == "__main__":
    sys.exit(main())
