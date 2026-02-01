import os

from fastapi.testclient import TestClient

from app.infra.db import add_ai_usage, init_db


def test_ai_cost_stats(tmp_path):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    os.environ["ADMIN_TOKEN"] = "secret"
    from app.config import get_settings
    get_settings.cache_clear()
    init_db()
    add_ai_usage("2026-01-21", 100, 50, 0.01, 0.01)
    from app.api.main import app
    client = TestClient(app)
    resp = client.get("/stats/ai_cost?date=2026-01-21", headers={"X-Admin-Token": "secret"})
    assert resp.status_code == 200
    assert resp.json()["total_cost_usd"] == 0.01
