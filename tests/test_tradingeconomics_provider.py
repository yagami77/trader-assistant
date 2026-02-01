import os

from app.config import get_settings
from app.infra.news_provider_tradingeconomics import TradingEconomicsProvider


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_tradingeconomics_provider_parses_and_filters(monkeypatch):
    payload = [
        {
            "Country": "United States",
            "Event": "CPI",
            "Importance": 3,
            "Date": "2026-01-21",
            "Time": "14:00",
        },
        {
            "Country": "Japan",
            "Event": "GDP",
            "Importance": 1,
            "Date": "2026-01-21",
            "Time": "10:00",
        },
    ]

    def fake_get(*args, **kwargs):
        return _Resp(payload)

    monkeypatch.setattr("app.infra.news_provider_tradingeconomics.httpx.get", fake_get)
    os.environ["TE_API_KEY"] = "guest:guest"
    os.environ["TE_BASE_URL"] = "https://api.tradingeconomics.com"
    os.environ["NEWS_COUNTRIES"] = "united states"
    os.environ["NEWS_IMPORTANCE_MIN"] = "2"
    os.environ["NEWS_LOOKAHEAD_HOURS"] = "24"
    os.environ["NEWS_CACHE_TTL_SEC"] = "300"
    os.environ["NEWS_TIMEOUT_SEC"] = "4"
    os.environ["NEWS_RETRY"] = "1"
    get_settings.cache_clear()

    provider = TradingEconomicsProvider()
    events = provider.get_events()
    assert len(events) == 1
    assert events[0].impact == "HIGH"
    assert events[0].title == "CPI"
