import os

from fastapi.testclient import TestClient


def _make_client(tmp_path, extra_env=None):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    for key in [
        "AI_ENABLED",
        "OPENAI_API_KEY",
        "TELEGRAM_ENABLED",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
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


def test_ai_disabled_fallback(tmp_path):
    client = _make_client(
        tmp_path,
        {"AI_ENABLED": "false", "TELEGRAM_ENABLED": "true", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"},
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["ai_output"] is None


def test_openai_error_fallback(monkeypatch, tmp_path):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.agents.coach_agent.generate_coach_message_from_payload", boom)
    client = _make_client(
        tmp_path,
        {"AI_ENABLED": "true", "TELEGRAM_ENABLED": "true", "OPENAI_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"},
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert "GO ✅" in resp.json()["message"] or "NO GO" in resp.json()["message"]
