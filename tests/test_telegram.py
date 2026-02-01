import json
import os

from fastapi.testclient import TestClient


def _make_client(tmp_path, extra_env=None):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    for key in [
        "ALWAYS_IN_SESSION",
        "MOCK_SERVER_TIME_UTC",
        "RR_MIN",
        "TRADING_SESSION_MODE",
        "MARKET_CLOSE_START",
        "MARKET_CLOSE_END",
        "MARKET_PROVIDER",
        "MT5_BRIDGE_URL",
        "DATA_MAX_AGE_SEC",
        "AI_ENABLED",
        "OPENAI_API_KEY",
        "NEWS_PREALERT_MINUTES",
        "TELEGRAM_ENABLED",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_SEND_NO_GO_IMPORTANT",
        "TELEGRAM_NO_GO_IMPORTANT_BLOCKS",
        "NEWS_CALENDAR_PATH",
    ]:
        os.environ.pop(key, None)
    if extra_env:
        for key, value in extra_env.items():
            os.environ[key] = value
    from app.config import get_settings
    from app.infra.db import init_db
    from app.api.main import app

    get_settings.cache_clear()
    init_db()
    return TestClient(app)


def test_telegram_go_sends(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_send(self, text):
        calls["count"] += 1
        return type("R", (), {"sent": True, "latency_ms": 5, "error": None})()

    monkeypatch.setattr("app.infra.telegram_sender.TelegramSender.send_message", fake_send)
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "true",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test",
            "TELEGRAM_CHAT_ID": "123",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["status"] in ["GO", "NO_GO"]
    assert calls["count"] == 1


def test_telegram_no_go_non_important_not_sent(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_send(self, text):
        calls["count"] += 1
        return type("R", (), {"sent": True, "latency_ms": 5, "error": None})()

    monkeypatch.setattr("app.infra.telegram_sender.TelegramSender.send_message", fake_send)
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "false",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T08:00:00+00:00",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test",
            "TELEGRAM_CHAT_ID": "123",
            "TELEGRAM_SEND_NO_GO_IMPORTANT": "true",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] == "OUT_OF_SESSION"
    assert calls["count"] == 0


def test_telegram_no_go_important_sent(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_send(self, text):
        calls["count"] += 1
        return type("R", (), {"sent": True, "latency_ms": 5, "error": None})()

    news_path = tmp_path / "news.json"
    news_path.write_text(
        json.dumps(
            [
                {
                    "datetime_iso": "2026-01-21T14:55:00+00:00",
                    "impact": "HIGH",
                    "title": "TEST NEWS",
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
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T14:45:00+00:00",
            "NEWS_CALENDAR_PATH": str(news_path),
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test",
            "TELEGRAM_CHAT_ID": "123",
            "TELEGRAM_SEND_NO_GO_IMPORTANT": "true",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] == "NEWS_LOCK"
    assert calls["count"] == 1


def test_telegram_duplicate_not_sent(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_send(self, text):
        calls["count"] += 1
        return type("R", (), {"sent": True, "latency_ms": 5, "error": None})()

    monkeypatch.setattr("app.infra.telegram_sender.TelegramSender.send_message", fake_send)
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "true",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T09:00:00+00:00",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test",
            "TELEGRAM_CHAT_ID": "123",
        },
    )
    first = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert first.status_code == 200
    second = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert second.status_code == 200
    assert second.json()["decision"]["blocked_by"] == "DUPLICATE_SIGNAL"
    assert calls["count"] == 1
