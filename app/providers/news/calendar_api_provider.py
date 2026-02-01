from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class CalendarApiEvent:
    id: str
    datetime_utc: str
    currency: str
    impact: str
    title: str
    source: str
    url: str | None = None


def _normalize_impact(value: str | None) -> str:
    raw = (value or "").strip().upper()
    if raw in {"HIGH", "H"}:
        return "HIGH"
    if raw in {"MED", "MEDIUM", "M"}:
        return "MEDIUM"
    if raw in {"LOW", "L"}:
        return "LOW"
    return "LOW"


def _impact_rank(value: str) -> int:
    mapping = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    return mapping.get(value, 0)


class CalendarApiProvider:
    def __init__(self) -> None:
        self._cache: List[CalendarApiEvent] | None = None
        self._cache_expiry = 0.0

    def get_events(self) -> List[CalendarApiEvent]:
        settings = get_settings()
        now = time.time()
        if self._cache and now < self._cache_expiry:
            return self._cache

        if not settings.news_api_base_url:
            raise RuntimeError("NEWS_API_BASE_URL manquant")

        headers: dict[str, str] = {}
        if settings.news_api_key:
            headers["Authorization"] = f"Bearer {settings.news_api_key}"

        currencies = {
            item.strip().upper()
            for item in settings.news_calendar_currencies.split(",")
            if item.strip()
        }
        impact_min = _normalize_impact(settings.news_calendar_impact_min)
        min_rank = _impact_rank(impact_min)

        params = {}
        if currencies:
            params["currencies"] = ",".join(sorted(currencies))
        if impact_min:
            params["impact_min"] = impact_min

        url = settings.news_api_base_url.rstrip("/") + "/calendar"
        last_exc: Exception | None = None
        attempts = max(1, settings.news_retry + 1)
        for _ in range(attempts):
            try:
                resp = httpx.get(url, headers=headers, params=params, timeout=settings.news_timeout_sec)
                resp.raise_for_status()
                payload = resp.json()
                items = payload.get("events", []) if isinstance(payload, dict) else []
                events: List[CalendarApiEvent] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    datetime_utc = (
                        item.get("datetime_utc")
                        or item.get("datetime_iso")
                        or item.get("datetime")
                        or item.get("time")
                    )
                    if not datetime_utc:
                        continue
                    currency = (item.get("currency") or item.get("ccy") or "").upper()
                    impact = _normalize_impact(item.get("impact") or item.get("impact_level"))
                    if currencies and currency not in currencies:
                        continue
                    if _impact_rank(impact) < min_rank:
                        continue
                    title = item.get("title") or item.get("event") or item.get("name") or "Event"
                    source = item.get("source") or payload.get("source") or "calendar_api"
                    url_value = item.get("url") or item.get("link")
                    event_id = str(
                        item.get("id")
                        or item.get("event_id")
                        or f"{currency}-{title}-{datetime_utc}"
                    )
                    events.append(
                        CalendarApiEvent(
                            id=event_id,
                            datetime_utc=datetime_utc,
                            currency=currency or "UNK",
                            impact=impact,
                            title=title,
                            source=source,
                            url=url_value,
                        )
                    )
                self._cache = events
                self._cache_expiry = now + settings.news_cache_ttl_sec
                return events
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        raise RuntimeError(f"Calendar API error: {last_exc}")
