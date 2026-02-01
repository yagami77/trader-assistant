from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class TelegramResult:
    sent: bool
    latency_ms: int
    error: Optional[str] = None


class TelegramSender:
    def __init__(self) -> None:
        self._settings = get_settings()

    def send_message(self, text: str) -> TelegramResult:
        if not self._settings.telegram_enabled:
            return TelegramResult(sent=False, latency_ms=0, error=None)

        if not self._settings.telegram_bot_token or not self._settings.telegram_chat_id:
            return TelegramResult(sent=False, latency_ms=0, error="Missing Telegram config")

        url = f"https://api.telegram.org/bot{self._settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": self._settings.telegram_chat_id, "text": text}
        last_error = None
        for attempt in range(2):
            start = time.perf_counter()
            try:
                resp = httpx.post(url, json=payload, timeout=3.0)
                latency_ms = int((time.perf_counter() - start) * 1000)
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}"
                    continue
                data = resp.json()
                if not data.get("ok", False):
                    last_error = "Telegram API not ok"
                    continue
                return TelegramResult(sent=True, latency_ms=latency_ms, error=None)
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt == 1:
                    break
        return TelegramResult(sent=False, latency_ms=0, error=last_error)
