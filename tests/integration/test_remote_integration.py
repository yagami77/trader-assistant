import os

import pytest
from fastapi.testclient import TestClient


def _make_client(tmp_path, extra_env=None):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    for key in [
        "MARKET_PROVIDER",
        "MT5_BRIDGE_URL",
        "DATA_MAX_AGE_SEC",
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


@pytest.mark.skipif(os.environ.get("RUN_REMOTE") != "1", reason="RUN_REMOTE!=1")
def test_remote_bridge_health(tmp_path):
    bridge_url = os.environ.get("MT5_BRIDGE_URL")
    assert bridge_url, "MT5_BRIDGE_URL required for remote tests"
    client = _make_client(
        tmp_path,
        {
            "MARKET_PROVIDER": "remote_mt5",
            "MT5_BRIDGE_URL": bridge_url,
            "DATA_MAX_AGE_SEC": "120",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] != "DATA_OFF"
