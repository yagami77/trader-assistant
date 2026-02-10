import os
import sqlite3

from app.config import get_settings
from app.infra.db import init_db, insert_signal


def test_ai_columns_insert(tmp_path):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    get_settings.cache_clear()
    init_db()
    insert_signal(
        {
            "ts_utc": "2026-01-01T00:00:00+00:00",
            "symbol": "XAUUSD",
            "tf_signal": "M15",
            "tf_context": "H1",
            "status": "GO",
            "blocked_by": None,
            "direction": "BUY",
            "entry": 1.0,
            "sl": 1.0,
            "tp1": 1.0,
            "tp2": 1.0,
            "rr_tp1": 1.5,
            "rr_tp2": 2.0,
            "score_total": 90,
            "score_effective": 90,
            "telegram_sent": 0,
            "telegram_error": None,
            "telegram_latency_ms": None,
            "alert_key": None,
            "score_rules_json": "{}",
            "ai_enabled": 1,
            "ai_output_json": None,
            "ai_model": "gpt-4o-mini",
            "ai_input_tokens": 100,
            "ai_output_tokens": 50,
            "ai_cost_usd": 0.01,
            "decision_packet_json": "{}",
            "signal_key": "k",
            "reasons_json": "{}",
            "message": "m",
            "data_latency_ms": 0,
            "ai_latency_ms": 10,
        }
    )
    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    row = conn.execute("SELECT ai_model, ai_cost_usd FROM signals").fetchone()
    conn.close()
    assert row[0] == "gpt-4o-mini"
