from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class TradingEconomicsEvent:
    id: str
    datetime_utc: str
    country: str
    impact: str
    title: str
    source: str


def _impact_from_importance(value: int | None) -> str:
    if value is None:
        return "LOW"
    if value >= 3:
        return "HIGH"
    if value == 2:
        return "MED"
    return "LOW"


class TradingEconomicsProvider:
    def __init__(self) -> None:
        self._cache: List[TradingEconomicsEvent] | None = None
        self._cache_expiry = 0.0

    def get_events(self) -> List[TradingEconomicsEvent]:
        settings = get_settings()
        now = time.time()
        if self._cache and now < self._cache_expiry:
            return self._cache

        if not settings.te_api_key:
            raise RuntimeError("TE_API_KEY manquant")

        countries = [c.strip() for c in settings.news_countries.split(",") if c.strip()]
        country_path = (countries[0] if countries else "united states").lower()

        now_utc = datetime.now(timezone.utc)
        end_utc = now_utc + timedelta(hours=settings.news_lookahead_hours)
        start_date = now_utc.strftime("%Y-%m-%d")
        end_date = end_utc.strftime("%Y-%m-%d")

        base_url = settings.te_base_url.rstrip("/")
        url = f"{base_url}/calendar/country/{country_path}/{start_date}/{end_date}"
        params = {"c": settings.te_api_key}

        last_exc: Exception | None = None
        for _ in range(max(1, settings.news_retry + 1)):
            try:
                resp = httpx.get(url, params=params, timeout=settings.news_timeout_sec)
                resp.raise_for_status()
                items = resp.json()
                if not isinstance(items, list):
                    items = []
                events = self._normalize(items, countries, settings.news_importance_min)
                self._cache = events
                self._cache_expiry = now + settings.news_cache_ttl_sec
                return events
            except Exception as exc:  # noqa: BLE001
                last_exc = exc

        fallback_url = f"{base_url}/calendar/country/{country_path}"
        try:
            resp = httpx.get(fallback_url, params=params, timeout=settings.news_timeout_sec)
            resp.raise_for_status()
            items = resp.json()
            if not isinstance(items, list):
                items = []
            events = self._normalize(items, countries, settings.news_importance_min)
            self._cache = events
            self._cache_expiry = now + settings.news_cache_ttl_sec
            return events
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"TradingEconomics error: {last_exc or exc}") from exc

    @staticmethod
    def _normalize(items: list, countries: list[str], importance_min: int) -> List[TradingEconomicsEvent]:
        normalized: List[TradingEconomicsEvent] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            country = str(item.get("Country") or item.get("country") or "").strip()
            if countries and country.lower() not in {c.lower() for c in countries}:
                continue
            importance = item.get("Importance") or item.get("importance")
            try:
                importance = int(importance)
            except Exception:
                importance = None
            if importance is not None and importance < importance_min:
                continue
            title = str(item.get("Event") or item.get("event") or item.get("Title") or "Event").strip()
            date_raw = item.get("Date") or item.get("date")
            time_raw = item.get("Time") or item.get("time")
            datetime_utc = TradingEconomicsProvider._build_datetime_utc(date_raw, time_raw)
            impact = _impact_from_importance(importance)
            stable_id = item.get("Id") or item.get("id")
            if not stable_id:
                raw = f"{title}|{country}|{datetime_utc}"
                stable_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()
            normalized.append(
                TradingEconomicsEvent(
                    id=str(stable_id),
                    datetime_utc=datetime_utc,
                    country=country or "Unknown",
                    impact=impact,
                    title=title or "Event",
                    source="TradingEconomics",
                )
            )
        return normalized

    @staticmethod
    def _build_datetime_utc(date_raw: str | None, time_raw: str | None) -> str:
        if not date_raw:
            return datetime.now(timezone.utc).isoformat()
        raw = str(date_raw).strip()
        if "T" in raw:
            try:
                dt = datetime.fromisoformat(raw)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                return datetime.now(timezone.utc).isoformat()
        try:
            dt = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            try:
                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                return datetime.now(timezone.utc).isoformat()
        if time_raw:
            try:
                tm = datetime.strptime(str(time_raw).strip(), "%H:%M").time()
                dt = dt.replace(hour=tm.hour, minute=tm.minute)
            except ValueError:
                pass
        return dt.replace(tzinfo=timezone.utc).isoformat()
