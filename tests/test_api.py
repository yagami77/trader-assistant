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
    os.environ.setdefault("MARKET_PROVIDER", "mock")
    from app.config import get_settings
    from app.api.main import app
    from app.infra.db import init_db

    get_settings.cache_clear()
    init_db()
    return TestClient(app)


def test_health(tmp_path):
    client = _make_client(tmp_path, {"ALWAYS_IN_SESSION": "true"})
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_analyze(tmp_path):
    client = _make_client(tmp_path, {"ALWAYS_IN_SESSION": "true"})
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    data = resp.json()
    assert "decision" in data
    assert "message" in data


def test_out_of_session(tmp_path):
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "false",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T10:00:00+00:00",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] == "OUT_OF_SESSION"


def test_news_lock(tmp_path):
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "true",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T14:45:00+00:00",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] == "NEWS_LOCK"


def test_rr_too_low(tmp_path):
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "true",
            "RR_MIN": "3.0",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] == "RR_TOO_LOW"


def test_duplicate_signal(tmp_path):
    client = _make_client(
        tmp_path,
        {
            "ALWAYS_IN_SESSION": "true",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T09:00:00+00:00",
        },
    )
    first = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert first.status_code == 200
    second = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert second.status_code == 200
    assert second.json()["decision"]["blocked_by"] == "DUPLICATE_SIGNAL"
