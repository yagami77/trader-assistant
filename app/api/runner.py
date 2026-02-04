"""Router /runner/status - état du runner."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = REPO_ROOT / "data" / "runner_state.json"

router = APIRouter(prefix="/runner", tags=["runner"])


@router.get("/status")
def runner_status() -> dict:
    """État du runner (dernier run, prochain ETA)."""
    default = {
        "last_run_utc": None,
        "last_http_status": None,
        "last_decision_status": None,
        "last_blocked_by": None,
        "last_score_total": None,
        "last_error": None,
        "next_run_eta_sec": None,
    }
    if not STATE_PATH.exists():
        return default
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return default

    result = {
        "last_run_utc": data.get("last_run_utc"),
        "last_http_status": data.get("last_http_status"),
        "last_decision_status": data.get("last_decision_status"),
        "last_blocked_by": data.get("last_blocked_by"),
        "last_score_total": data.get("last_score_total"),
        "last_error": data.get("last_error"),
        "next_run_eta_sec": None,
    }

    interval = data.get("interval_sec", 300)
    last_utc = data.get("last_run_utc")
    if last_utc:
        try:
            last_dt = datetime.fromisoformat(last_utc.replace("Z", "+00:00"))
            next_run = last_dt.timestamp() + interval
            now = datetime.now(timezone.utc).timestamp()
            eta = int(next_run - now)
            result["next_run_eta_sec"] = max(0, eta)
        except Exception:
            pass

    return result
