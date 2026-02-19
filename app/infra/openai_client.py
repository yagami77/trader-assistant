from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class OpenAIResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def generate_coach_message(prompt: str) -> OpenAIResult:
    settings = get_settings()
    if not settings.ai_enabled:
        raise RuntimeError("AI disabled")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY manquant")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    payload = {
        "model": settings.ai_model,
        "temperature": 0.2,
        "max_tokens": settings.ai_max_tokens_per_message,
        "messages": [{"role": "user", "content": prompt}],
    }
    last_exc: Optional[Exception] = None
    for _ in range(2):
        start = time.perf_counter()
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=settings.ai_timeout_sec)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return OpenAIResult(
                text=content,
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"OpenAI error: {last_exc}")


def generate_analyst_message(prompt: str, max_tokens: Optional[int] = None) -> OpenAIResult:
    """Appel OpenAI pour l'agent analyste — max_tokens élevé, explications généreuses."""
    settings = get_settings()
    tokens = max_tokens or getattr(settings, "ai_analyst_max_tokens", 2500)
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    payload = {
        "model": settings.ai_model,
        "temperature": 0.3,
        "max_tokens": tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    start = time.perf_counter()
    resp = httpx.post(url, json=payload, headers=headers, timeout=min(60, settings.ai_timeout_sec * 4))
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return OpenAIResult(
        text=content,
        input_tokens=int(usage.get("prompt_tokens", 0)),
        output_tokens=int(usage.get("completion_tokens", 0)),
        latency_ms=int((time.perf_counter() - start) * 1000),
    )


call_chat_completion = generate_coach_message
