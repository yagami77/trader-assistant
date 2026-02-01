from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.e2e.helpers import (
    analyze,
    count_signals,
    restore_news,
    run_api,
    set_state_budget_reached,
    write_news_with_event,
)


def test_out_of_session():
    with run_api(
        {
            "ALWAYS_IN_SESSION": "false",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T08:00:00+00:00",
        }
    ) as (base_url, _):
        data = analyze(base_url)
        assert data["decision"]["blocked_by"] == "OUT_OF_SESSION"
        assert data["decision"]["score_effective"] == 0


def test_news_lock():
    now_utc = datetime(2026, 1, 21, 14, 45, tzinfo=timezone.utc)
    backup = write_news_with_event(now_utc + timedelta(minutes=10))
    try:
        with run_api(
            {
                "ALWAYS_IN_SESSION": "true",
                "TRADING_SESSION_MODE": "windows",
                "MOCK_SERVER_TIME_UTC": now_utc.isoformat(),
            }
        ) as (base_url, _):
            data = analyze(base_url)
            assert data["decision"]["blocked_by"] == "NEWS_LOCK"
            assert data["decision"]["score_effective"] == 0
    finally:
        restore_news(backup)


def test_duplicate_signal():
    with run_api(
        {
            "ALWAYS_IN_SESSION": "true",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T09:00:00+00:00",
        }
    ) as (base_url, db_path):
        before = count_signals(db_path)
        first = analyze(base_url)
        assert first["decision"]["status"] in ["GO", "NO_GO"]
        assert first["decision"]["score_effective"] == first["decision"]["score_total"]
        after_first = count_signals(db_path)
        second = analyze(base_url)
        assert second["decision"]["blocked_by"] == "DUPLICATE_SIGNAL"
        assert second["decision"]["score_effective"] == 0
        after_second = count_signals(db_path)
        assert after_first - before == 1
        assert after_second - after_first == 1


def test_rr_too_low():
    with run_api(
        {
            "ALWAYS_IN_SESSION": "true",
            "RR_MIN": "10.0",
        }
    ) as (base_url, _):
        data = analyze(base_url)
        assert data["decision"]["blocked_by"] == "RR_TOO_LOW"
        assert data["decision"]["score_effective"] == 0


def test_daily_budget_reached():
    with run_api(
        {
            "ALWAYS_IN_SESSION": "true",
            "TRADING_SESSION_MODE": "windows",
            "MOCK_SERVER_TIME_UTC": "2026-01-21T09:00:00+00:00",
        }
    ) as (base_url, db_path):
        set_state_budget_reached(db_path, "2026-01-21")
        data = analyze(base_url)
        assert data["decision"]["blocked_by"] == "DAILY_BUDGET_REACHED"
        assert data["decision"]["score_effective"] == 0


def test_data_off():
    with run_api(
        {
            "ALWAYS_IN_SESSION": "true",
            "MOCK_PROVIDER_FAIL": "true",
        }
    ) as (base_url, _):
        data = analyze(base_url)
        assert data["decision"]["blocked_by"] == "DATA_OFF"
        assert data["decision"]["score_effective"] == 0
