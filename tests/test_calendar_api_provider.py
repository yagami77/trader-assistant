import os

from app.config import get_settings
from app.providers.news.calendar_api_provider import CalendarApiProvider


class _Resp:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_calendar_api_provider_filters_and_normalizes(monkeypatch):
    payload = {
        "source": "calendar_api",
        "events": [
            {
                "id": 1,
                "datetime_utc": "2026-01-21T14:00:00+00:00",
                "currency": "USD",
                "impact": "high",
                "title": "CPI",
                "url": "https://example.com/1",
            },
            {
                "id": 2,
                "datetime_utc": "2026-01-21T15:00:00+00:00",
                "currency": "JPY",
                "impact": "low",
                "title": "Test",
            },
            {
                "id": 3,
                "datetime_utc": "2026-01-21T16:00:00+00:00",
                "currency": "EUR",
                "impact": "MED",
                "title": "PMI",
            },
        ],
    }

    def fake_get(*args, **kwargs):
        return _Resp(payload)

    monkeypatch.setattr("app.providers.news.calendar_api_provider.httpx.get", fake_get)

    os.environ["NEWS_API_BASE_URL"] = "https://calendar.example"
    os.environ["NEWS_API_KEY"] = "test"
    os.environ["NEWS_CACHE_TTL_SEC"] = "300"
    os.environ["NEWS_TIMEOUT_SEC"] = "4"
    os.environ["NEWS_RETRY"] = "1"
    os.environ["NEWS_CALENDAR_CURRENCIES"] = "USD,EUR"
    os.environ["NEWS_CALENDAR_IMPACT_MIN"] = "HIGH"
    get_settings.cache_clear()

    provider = CalendarApiProvider()
    events = provider.get_events()

    assert len(events) == 1
    event = events[0]
    assert event.currency == "USD"
    assert event.impact == "HIGH"
    assert event.title == "CPI"
