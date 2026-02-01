from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.providers.news_calendar_provider import NewsEvent


@dataclass(frozen=True)
class NewsTimingState:
    minutes_to_event: Optional[int]
    lock_window_start_min: int
    lock_window_end_min: int
    moment_label: str
    horizon_minutes: int
    should_pre_alert: bool
    lock_active: bool
    lock_reason: Optional[str]
    bucket_label: Optional[str]


def _parse_minutes_list(value: str) -> List[int]:
    items = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            items.append(int(part))
        except ValueError:
            continue
    return items


def compute_news_timing(
    now: datetime,
    event: Optional[NewsEvent],
    high_pre_min: int,
    high_post_min: int,
    med_pre_min: int,
    med_post_min: int,
    prealert_minutes: str,
) -> NewsTimingState:
    if not event:
        return NewsTimingState(
            minutes_to_event=None,
            lock_window_start_min=-high_pre_min,
            lock_window_end_min=high_post_min,
            moment_label="",
            horizon_minutes=0,
            should_pre_alert=False,
            lock_active=False,
            lock_reason=None,
            bucket_label=None,
        )

    try:
        event_ts = datetime.fromisoformat(event.datetime_iso)
    except ValueError:
        return NewsTimingState(
            minutes_to_event=None,
            lock_window_start_min=-high_pre_min,
            lock_window_end_min=high_post_min,
            moment_label="",
            horizon_minutes=0,
            should_pre_alert=False,
            lock_active=False,
            lock_reason=None,
            bucket_label=None,
        )
    delta_min = int(round((event_ts - now).total_seconds() / 60))
    impact = event.impact.upper()
    if impact == "HIGH":
        lock_start = -high_pre_min
        lock_end = high_post_min
    elif impact in {"MED", "MEDIUM"}:
        lock_start = -med_pre_min
        lock_end = med_post_min
    else:
        lock_start = 0
        lock_end = 0
    lock_active = lock_start <= delta_min <= lock_end if lock_start or lock_end else False
    lock_reason = f"{impact} impact news" if lock_active else None

    if delta_min <= 0:
        moment = "NOW"
        horizon_minutes = high_post_min if impact == "HIGH" else med_post_min if impact in {"MED", "MEDIUM"} else 30
    elif delta_min <= 90:
        moment = "NEXT_30_90_MIN"
        horizon_minutes = high_post_min if impact == "HIGH" else med_post_min if impact in {"MED", "MEDIUM"} else 90
    elif delta_min <= 600:
        moment = "LATER_TODAY"
        horizon_minutes = high_post_min if impact == "HIGH" else med_post_min if impact in {"MED", "MEDIUM"} else 240
    else:
        moment = "SWING"
        horizon_minutes = high_post_min if impact == "HIGH" else med_post_min if impact in {"MED", "MEDIUM"} else 1440

    prealert_list = _parse_minutes_list(prealert_minutes)
    should_pre_alert = delta_min in prealert_list and impact in {"HIGH", "MED", "MEDIUM"}
    bucket_label = f"T-{delta_min}" if should_pre_alert else None

    return NewsTimingState(
        minutes_to_event=delta_min,
        lock_window_start_min=lock_start,
        lock_window_end_min=lock_end,
        moment_label=moment,
        horizon_minutes=horizon_minutes,
        should_pre_alert=should_pre_alert,
        lock_active=lock_active,
        lock_reason=lock_reason,
        bucket_label=bucket_label,
    )
