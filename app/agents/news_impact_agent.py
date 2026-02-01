from __future__ import annotations

from typing import List, Optional

from app.providers.news_calendar_provider import NewsEvent


def build_news_impact_summary(event: Optional[NewsEvent]) -> List[str]:
    if not event:
        return []
    impact = event.impact.upper()
    title = event.title.lower()
    currency = (event.currency or "").upper()
    bullets: List[str] = []

    if impact == "HIGH":
        bullets.append("Volatilite probable autour de la publication.")

    if currency == "USD" or "fed" in title or "cpi" in title or "inflation" in title:
        bullets.append("USD fort peut peser sur l'or; USD faible peut soutenir l'or.")
    elif currency in {"EUR", "GBP"}:
        bullets.append("Effet indirect via USD; impact XAUUSD souvent modere.")
    else:
        bullets.append("Impact directionnel incertain; prudence recommandee.")

    return bullets[:2]
