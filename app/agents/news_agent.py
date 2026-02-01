from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from app.config import get_settings
from app.providers.news_calendar_provider import HttpNewsCalendarProvider
from app.providers.news.calendar_api_provider import CalendarApiProvider
from app.infra.news_provider_tradingeconomics import TradingEconomicsProvider


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

    @property
    def timestamp(self) -> datetime:
        ts = datetime.fromisoformat(self.datetime_iso)
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts


def _load_calendar() -> List[NewsEvent]:
    settings = get_settings()
    path = Path(settings.news_calendar_path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [NewsEvent(**item) for item in raw]


def _load_from_api() -> List[NewsEvent]:
    events = _HTTP_PROVIDER.get_events()
    return [
        NewsEvent(
            datetime_iso=event.datetime_iso,
            impact=event.impact,
            title=event.title,
            currency=getattr(event, "currency", None),
            country=getattr(event, "country", None),
            actual=getattr(event, "actual", None),
            forecast=getattr(event, "forecast", None),
            previous=getattr(event, "previous", None),
        )
        for event in events
    ]


def _load_from_calendar_api() -> List[NewsEvent]:
    events = _CALENDAR_PROVIDER.get_events()
    return [
        NewsEvent(
            datetime_iso=event.datetime_utc,
            impact=event.impact,
            title=event.title,
            currency=getattr(event, "currency", None),
            country=None,
            actual=None,
            forecast=None,
            previous=None,
        )
        for event in events
    ]


def _load_from_tradingeconomics() -> List[NewsEvent]:
    events = _TE_PROVIDER.get_events()
    return [
        NewsEvent(
            datetime_iso=event.datetime_utc,
            impact=event.impact,
            title=event.title,
            currency=event.country,
            country=event.country,
        )
        for event in events
    ]


def _next_event(events: List[NewsEvent], now: datetime) -> Optional[NewsEvent]:
    upcoming = [event for event in events if event.timestamp >= now]
    return min(upcoming, key=lambda ev: ev.timestamp, default=None)


def _lock_window_for(event: NewsEvent, high_pre: int, high_post: int, med_pre: int, med_post: int) -> Tuple[int, int]:
    impact = event.impact.upper()
    if impact == "HIGH":
        return -high_pre, high_post
    if impact in {"MED", "MEDIUM"}:
        return -med_pre, med_post
    return 0, 0


_HTTP_PROVIDER = HttpNewsCalendarProvider()
_CALENDAR_PROVIDER = CalendarApiProvider()
_TE_PROVIDER = TradingEconomicsProvider()


def get_lock(
    now: datetime,
    high_pre_min: int,
    high_post_min: int,
    med_pre_min: int,
    med_post_min: int,
) -> Tuple[bool, Optional[NewsEvent], bool, int, Tuple[int, int]]:
    settings = get_settings()
    provider_name = settings.news_provider.lower()
    calendar: List[NewsEvent] = []
    provider_ok = True

    try:
        if provider_name == "tradingeconomics":
            calendar = _load_from_tradingeconomics()
        elif provider_name == "calendar_api":
            calendar = _load_from_calendar_api()
        elif provider_name == "api":
            calendar = _load_from_api()
        else:
            calendar = _load_calendar()
    except Exception:
        provider_ok = False
        if settings.news_fallback_to_mock and provider_name in {"api", "calendar_api"}:
            calendar = _load_calendar()
        else:
            calendar = []

    next_event = _next_event(calendar, now)
    if not next_event:
        return False, None, provider_ok, len(calendar), (0, 0)

    lock_start, lock_end = _lock_window_for(next_event, high_pre_min, high_post_min, med_pre_min, med_post_min)
    if lock_start == 0 and lock_end == 0:
        return False, next_event, provider_ok, len(calendar), (0, 0)

    delta = next_event.timestamp - now
    lock_active = delta <= timedelta(minutes=lock_end) and delta >= timedelta(minutes=lock_start)
    return lock_active, next_event, provider_ok, len(calendar), (lock_start, lock_end)
