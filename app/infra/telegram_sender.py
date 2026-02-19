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

    def send_message(self, text: str, chat_id: Optional[str] = None) -> TelegramResult:
        if not self._settings.telegram_enabled:
            return TelegramResult(
                sent=False, latency_ms=0, error="TELEGRAM_ENABLED=false (processus n'a pas chargé .env?)"
            )

        target = (chat_id or "").strip() or self._settings.telegram_chat_id
        if not self._settings.telegram_bot_token or not target:
            return TelegramResult(sent=False, latency_ms=0, error="Missing Telegram config")

        # Normaliser le texte pour éviter erreurs d'encodage (Telegram attend UTF-8)
        try:
            if not isinstance(text, str):
                text = str(text)
            text = text.encode("utf-8", errors="replace").decode("utf-8")
        except Exception as e:  # noqa: BLE001
            return TelegramResult(sent=False, latency_ms=0, error=f"Encodage message: {e!s}")

        url = f"https://api.telegram.org/bot{self._settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": target, "text": text}
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
