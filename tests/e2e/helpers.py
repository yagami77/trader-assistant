from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Generator, List, Tuple

import httpx
import sqlite3


REPO_ROOT = Path(__file__).resolve().parents[2]
NEWS_PATH = REPO_ROOT / "data" / "news_calendar_mock.json"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_health(base_url: str, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base_url}/health", timeout=1.0)
            if resp.status_code == 200 and resp.json().get("status") == "ok":
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("API health check failed")


@contextmanager
def run_api(env_overrides: Dict[str, str]) -> Generator[Tuple[str, Path], None, None]:
    port = free_port()
    db_path = REPO_ROOT / "data" / f"test_{port}.db"
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "DATABASE_PATH": str(db_path),
            "LOG_LEVEL": "INFO",
            "MARKET_PROVIDER": "mock",
        }
    )
    env.update(env_overrides)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        wait_health(base_url)
        yield base_url, db_path
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        if db_path.exists():
            db_path.unlink()


def analyze(base_url: str) -> Dict:
    resp = httpx.post(f"{base_url}/analyze", json={"symbol": "XAUUSD"}, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


def write_news_with_event(event_time: datetime) -> Dict:
    original = json.loads(NEWS_PATH.read_text(encoding="utf-8"))
    backup = {"events": original}
    news = [
        {
            "datetime_iso": event_time.isoformat(),
            "impact": "HIGH",
            "title": "TEST NEWS",
        }
    ]
    NEWS_PATH.write_text(json.dumps(news, ensure_ascii=True, indent=2), encoding="utf-8")
    return backup


def restore_news(backup: Dict) -> None:
    NEWS_PATH.write_text(json.dumps(backup["events"], ensure_ascii=True, indent=2), encoding="utf-8")


def set_state_budget_reached(db_path: Path, day_paris: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT OR REPLACE INTO state (
            day_paris, daily_loss_amount, daily_budget_amount,
            last_signal_key, last_ts, consecutive_losses
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (day_paris, 100.0, 20.0, None, None, 0),
    )
    conn.commit()
    conn.close()


def fetch_signal_rows(db_path: Path, limit: int = 5) -> List[Dict[str, str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT status, blocked_by, score_total, score_effective, decision_packet_json FROM signals ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def count_signals(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT COUNT(*) FROM signals").fetchone()
    conn.close()
    return int(row[0])


def measure_latency(base_url: str, calls: int = 10) -> Dict[str, float]:
    times: List[float] = []
    for _ in range(calls):
        start = time.perf_counter()
        analyze(base_url)
        times.append(time.perf_counter() - start)
    return {
        "min": min(times),
        "avg": sum(times) / len(times),
        "max": max(times),
    }
