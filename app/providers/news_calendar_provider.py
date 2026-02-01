from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Protocol

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class NewsEvent:
    datetime_iso: str
    impact: str
    title: str
    currency: str | None = None
    country: str | None = None
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None


class NewsCalendarProvider(Protocol):
    def get_events(self) -> List[NewsEvent]:
        ...


class HttpNewsCalendarProvider:
    def __init__(self) -> None:
        self._cache: List[NewsEvent] | None = None
        self._cache_expiry = 0.0

    def get_events(self) -> List[NewsEvent]:
        now = time.time()
        if self._cache and now < self._cache_expiry:
            return self._cache

        settings = get_settings()
        if not settings.news_api_base_url:
            raise RuntimeError("NEWS_API_BASE_URL manquant")
        headers = {}
        if settings.news_api_key:
            headers["Authorization"] = f"Bearer {settings.news_api_key}"

        url = settings.news_api_base_url.rstrip("/") + "/events"
        last_exc: Exception | None = None
        for _ in range(max(1, settings.news_retry + 1)):
            try:
                resp = httpx.get(url, headers=headers, timeout=settings.news_timeout_sec)
                resp.raise_for_status()
                payload = resp.json()
                events = [
                    NewsEvent(
                        datetime_iso=item["datetime_iso"],
                        impact=item["impact"],
                        title=item["title"],
                        currency=item.get("currency"),
                        country=item.get("country"),
                        actual=item.get("actual"),
                        forecast=item.get("forecast"),
                        previous=item.get("previous"),
                    )
                    for item in payload.get("events", [])
                ]
                self._cache = events
                self._cache_expiry = now + settings.news_cache_ttl_sec
                return events
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        raise RuntimeError(f"News provider error: {last_exc}")
