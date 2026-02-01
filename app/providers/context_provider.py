from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Protocol

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class ContextItem:
    title: str
    detail: str


class ContextProvider(Protocol):
    def get_context(self) -> List[ContextItem]:
        ...


class HttpContextProvider:
    def __init__(self) -> None:
        self._cache: List[ContextItem] | None = None
        self._cache_expiry = 0.0

    def get_context(self) -> List[ContextItem]:
        now = time.time()
        if self._cache and now < self._cache_expiry:
            return self._cache

        settings = get_settings()
        if not settings.context_api_base_url:
            raise RuntimeError("CONTEXT_API_BASE_URL manquant")
        headers = {}
        if settings.context_api_key:
            headers["Authorization"] = f"Bearer {settings.context_api_key}"

        url = settings.context_api_base_url.rstrip("/") + "/context"
        last_exc: Exception | None = None
        for _ in range(2):
            try:
                resp = httpx.get(url, headers=headers, timeout=4.0)
                resp.raise_for_status()
                payload = resp.json()
                items = [
                    ContextItem(title=item["title"], detail=item["detail"])
                    for item in payload.get("items", [])
                ]
                self._cache = items
                self._cache_expiry = now + 300
                return items
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        raise RuntimeError(f"Context provider error: {last_exc}")
