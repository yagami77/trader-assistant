#!/usr/bin/env bash
set -euo pipefail

if [ -z "${TE_API_KEY:-}" ]; then
  echo "TE_API_KEY manquant"
  exit 1
fi

python - <<'PY'
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.infra.news_provider_tradingeconomics import TradingEconomicsProvider
from app.agents.news_agent import NewsEvent
from app.engines.news_timing import compute_news_timing

settings = get_settings()
provider = TradingEconomicsProvider()
events = provider.get_events()

print(f"Events fetched: {len(events)}")
if events:
    first = events[0]
    print("Sample event:")
    print(
        {
            "id": first.id,
            "datetime_utc": first.datetime_utc,
            "currency": first.currency,
            "impact": first.impact,
            "title": first.title,
            "source": first.source,
            "url": first.url,
        }
    )

now = datetime.now(timezone.utc)
test_event = NewsEvent(
    datetime_iso=(now + timedelta(minutes=10)).isoformat(),
    impact="HIGH",
    title="TEST_EVENT",
)
state = compute_news_timing(
    now,
    test_event,
    settings.news_lock_high_pre_min,
    settings.news_lock_high_post_min,
    settings.news_lock_med_pre_min,
    settings.news_lock_med_post_min,
    settings.news_prealert_minutes,
)
print("Lock active:", state.lock_active)
print("Moment:", state.moment_label, "Horizon:", state.horizon_minutes)
PY
