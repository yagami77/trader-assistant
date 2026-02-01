from __future__ import annotations

from typing import List, Tuple

from app.config import get_settings
from app.providers.context_provider import HttpContextProvider


def get_context_summary() -> Tuple[List[str], List[str]]:
    settings = get_settings()
    if not settings.context_enabled:
        return [], []
    provider = HttpContextProvider()
    try:
        items = provider.get_context()
    except Exception:
        return ["Contexte indisponible"], ["context:api"]
    if not items:
        return ["Contexte indisponible"], ["context:api"]
    bullets = [f"{item.title}: {item.detail}" for item in items][:4]
    return bullets, ["context:api"]
