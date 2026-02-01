import json
import os

from fastapi.testclient import TestClient


def _make_client(tmp_path, extra_env=None):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    for key in [
        "ALWAYS_IN_SESSION",
        "MOCK_SERVER_TIME_UTC",
        "NEWS_CALENDAR_PATH",
        "NEWS_PREALERT_MINUTES",
        "AI_ENABLED",
        "TELEGRAM_ENABLED",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "MARKET_PROVIDER",
        "MT5_BRIDGE_URL",
        "DATA_MAX_AGE_SEC",
    ]:
        os.environ.pop(key, None)
    if extra_env:
        for key, value in extra_env.items():
            os.environ[key] = value
    os.environ["MARKET_PROVIDER"] = "mock"
    from app.config import get_settings
    from app.infra.db import init_db
    from app.api.main import app

    get_settings.cache_clear()
    init_db()
    return TestClient(app)


def test_prealert_sent_once(monkeypatch, tmp_path):
    sent_texts = []

    def fake_send(self, text):
        sent_texts.append(text)
        return type("R", (), {"sent": True, "latency_ms": 5, "error": None})()

    news_path = tmp_path / "news.json"
    news_path.write_text(
        json.dumps(
            [
                {
                    "datetime_iso": "2026-01-21T15:00:00+00:00",
                    "impact": "HIGH",
                    "title": "CPI",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.infra.telegram_sender.TelegramSender.send_message", fake_send)
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "true",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T14:00:00+00:00",
            "NEWS_CALENDAR_PATH": str(news_path),
            "NEWS_PREALERT_MINUTES": "60",
            "AI_ENABLED": "false",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test",
            "TELEGRAM_CHAT_ID": "123",
        },
    )
    client.post("/analyze", json={"symbol": "XAUUSD"})
    client.post("/analyze", json={"symbol": "XAUUSD"})

    # verify anti-spam via alert_key persisted once
    import sqlite3

    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    row = conn.execute("SELECT COUNT(*) FROM signals WHERE alert_key IS NOT NULL").fetchone()
    conn.close()
    assert row[0] == 1
