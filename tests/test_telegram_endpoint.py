import os

from fastapi.testclient import TestClient


def _make_client(tmp_path, extra_env=None):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    for key in [
        "ADMIN_TOKEN",
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


def test_telegram_test_endpoint_ok(monkeypatch, tmp_path):
    def fake_send(self, text):
        return type("R", (), {"sent": True, "latency_ms": 7, "error": None})()

    monkeypatch.setattr("app.infra.telegram_sender.TelegramSender.send_message", fake_send)
    client = _make_client(
        tmp_path,
        {
            "ADMIN_TOKEN": "secret",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test",
            "TELEGRAM_CHAT_ID": "123",
        },
    )
    resp = client.post(
        "/telegram/test",
        headers={"X-Admin-Token": "secret"},
        json={"text": "Ping"},
    )
    assert resp.status_code == 200
    assert resp.json()["sent"] is True


def test_telegram_test_endpoint_missing_chat(tmp_path):
    client = _make_client(tmp_path, {"ADMIN_TOKEN": "secret"})
    resp = client.post("/telegram/test", headers={"X-Admin-Token": "secret"})
    assert resp.status_code == 400
