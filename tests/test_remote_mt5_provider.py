from datetime import datetime, timedelta, timezone

import httpx
from fastapi.testclient import TestClient


def _make_client(tmp_path, extra_env=None):
    import os

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


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._payload


def test_remote_bridge_down(monkeypatch, tmp_path):
    def fake_get(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", fake_get)
    client = _make_client(
        tmp_path,
        {
            "MARKET_PROVIDER": "remote_mt5",
            "MT5_BRIDGE_URL": "http://bridge",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] == "DATA_OFF"


def test_remote_stale_candles(monkeypatch, tmp_path):
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    fresh_ts = datetime.now(timezone.utc).isoformat()

    def fake_get(url, params=None, timeout=4.0, headers=None):
        if url.endswith("/candles"):
            return FakeResponse({"candles": [{"ts": old_ts, "open": 1, "high": 1, "low": 1, "close": 1}]})
        if url.endswith("/spread"):
            return FakeResponse({"spread_points": 12, "bid": 1, "ask": 1, "ts": fresh_ts})
        if url.endswith("/tick"):
            return FakeResponse({"bid": 1, "ask": 1, "ts": fresh_ts})
        return FakeResponse({}, status_code=404)

    monkeypatch.setattr(httpx, "get", fake_get)
    client = _make_client(
        tmp_path,
        {
            "MARKET_PROVIDER": "remote_mt5",
            "MT5_BRIDGE_URL": "http://bridge",
            "DATA_MAX_AGE_SEC": "120",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] == "DATA_OFF"


def test_remote_ok(monkeypatch, tmp_path):
    fresh_ts = datetime.now(timezone.utc).isoformat()

    def fake_get(url, params=None, timeout=4.0, headers=None):
        if url.endswith("/candles"):
            return FakeResponse({"candles": [{"ts": fresh_ts, "open": 4660, "high": 4685, "low": 4645, "close": 4672}]})
        if url.endswith("/spread"):
            return FakeResponse({"spread_points": 12, "bid": 4671.5, "ask": 4672.0, "ts": fresh_ts})
        if url.endswith("/tick"):
            return FakeResponse({"bid": 4671.5, "ask": 4672.0, "ts": fresh_ts})
        return FakeResponse({}, status_code=404)

    monkeypatch.setattr(httpx, "get", fake_get)
    client = _make_client(
        tmp_path,
        {
            "MARKET_PROVIDER": "remote_mt5",
            "MT5_BRIDGE_URL": "http://bridge",
            "DATA_MAX_AGE_SEC": "120",
        },
    )
    resp = client.post("/analyze", json={"symbol": "XAUUSD"})
    assert resp.status_code == 200
    assert resp.json()["decision"]["blocked_by"] != "DATA_OFF"
