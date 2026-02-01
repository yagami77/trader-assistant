from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.providers.news_calendar_provider import HttpNewsCalendarProvider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._payload


def test_news_provider_http(monkeypatch):
    def fake_get(url, headers=None, timeout=4.0):
        return FakeResponse(
            {
                "events": [
                    {
                        "datetime_iso": "2026-01-21T14:55:00+00:00",
                        "impact": "HIGH",
                        "title": "CPI",
                        "currency": "USD",
                        "country": "US",
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setenv("NEWS_API_BASE_URL", "https://example.com")
    get_settings.cache_clear()
    provider = HttpNewsCalendarProvider()
    events = provider.get_events()
    assert events[0].impact == "HIGH"


def test_news_lock_high_near(monkeypatch):
    from app.agents.news_agent import get_lock

    def fake_get_events(self):
        return [
            type(
                "E",
                (),
                {
                    "datetime_iso": "2026-01-21T14:55:00+00:00",
                    "impact": "HIGH",
                    "title": "CPI",
                },
            )()
        ]

    monkeypatch.setenv("NEWS_PROVIDER", "api")
    monkeypatch.setenv("NEWS_API_BASE_URL", "https://example.com")
    get_settings.cache_clear()
    monkeypatch.setattr("app.providers.news_calendar_provider.HttpNewsCalendarProvider.get_events", fake_get_events)
    locked, _, _, _, _ = get_lock(datetime(2026, 1, 21, 14, 45, tzinfo=timezone.utc), 30, 90, 10, 5)
    assert locked is True


def test_news_lock_high_far(monkeypatch):
    from app.agents.news_agent import get_lock

    def fake_get_events(self):
        return [
            type(
                "E",
                (),
                {
                    "datetime_iso": "2026-01-21T20:00:00+00:00",
                    "impact": "HIGH",
                    "title": "CPI",
                },
            )()
        ]

    monkeypatch.setenv("NEWS_PROVIDER", "api")
    monkeypatch.setenv("NEWS_API_BASE_URL", "https://example.com")
    get_settings.cache_clear()
    monkeypatch.setattr("app.providers.news_calendar_provider.HttpNewsCalendarProvider.get_events", fake_get_events)
    locked, _, _, _, _ = get_lock(datetime(2026, 1, 21, 14, 45, tzinfo=timezone.utc), 30, 90, 10, 5)
    assert locked is False


def test_news_lock_med_window(monkeypatch):
    from app.agents.news_agent import get_lock

    def fake_get_events(self):
        return [
            type(
                "E",
                (),
                {
                    "datetime_iso": "2026-01-21T14:55:00+00:00",
                    "impact": "MED",
                    "title": "Retail Sales",
                },
            )()
        ]

    monkeypatch.setenv("NEWS_PROVIDER", "api")
    monkeypatch.setenv("NEWS_API_BASE_URL", "https://example.com")
    get_settings.cache_clear()
    monkeypatch.setattr("app.providers.news_calendar_provider.HttpNewsCalendarProvider.get_events", fake_get_events)
    locked, _, _, _, _ = get_lock(datetime(2026, 1, 21, 14, 50, tzinfo=timezone.utc), 30, 90, 10, 5)
    assert locked is True
