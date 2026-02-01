from datetime import datetime, timezone, timedelta

from app.engines.news_timing import compute_news_timing
from app.providers.news_calendar_provider import NewsEvent


def test_news_timing_lock_and_horizon():
    now = datetime(2026, 1, 21, 14, 30, tzinfo=timezone.utc)
    event = NewsEvent(
        datetime_iso=(now + timedelta(minutes=10)).isoformat(),
        impact="HIGH",
        title="CPI",
    )
    state = compute_news_timing(
        now,
        event,
        high_pre_min=30,
        high_post_min=90,
        med_pre_min=10,
        med_post_min=5,
        prealert_minutes="60,30,15",
    )
    assert state.lock_active is True
    assert state.moment_label == "NEXT_30_90_MIN"
    assert state.horizon_minutes == 90
    assert state.should_pre_alert is False


def test_news_timing_prealert():
    now = datetime(2026, 1, 21, 14, 0, tzinfo=timezone.utc)
    event = NewsEvent(
        datetime_iso=(now + timedelta(minutes=60)).isoformat(),
        impact="HIGH",
        title="CPI",
    )
    state = compute_news_timing(
        now,
        event,
        high_pre_min=30,
        high_post_min=90,
        med_pre_min=10,
        med_post_min=5,
        prealert_minutes="60,30,15",
    )
    assert state.should_pre_alert is True
    assert state.bucket_label == "T-60"
