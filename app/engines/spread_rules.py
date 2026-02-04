from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from app.config import get_settings
from app.models import DecisionPacket


@dataclass(frozen=True)
class SpreadEvaluation:
    spread_points: float
    sl_points: Optional[float]
    spread_ratio: Optional[float]
    points_penalty: int
    ratio_penalty: int
    penalty: int


def _linear_penalty(value: float, start: float, end: float, max_penalty: int) -> int:
    if end <= start:
        return 0
    if value <= start:
        return 0
    if value >= end:
        return int(max_penalty)
    ratio = (value - start) / (end - start)
    return int(round(ratio * max_penalty))


def evaluate_spread(packet: DecisionPacket) -> SpreadEvaluation:
    settings = get_settings()
    spread_points = float(packet.spread)
    sl_points: Optional[float] = None
    spread_ratio: Optional[float] = None
    if packet.sl and packet.proposed_entry and packet.tick_size > 0:
        sl_points = abs(packet.proposed_entry - packet.sl) / packet.tick_size
        if sl_points > 0:
            spread_ratio = spread_points / sl_points

    points_penalty = _linear_penalty(
        spread_points,
        settings.soft_spread_start_points,
        settings.hard_spread_max_points,
        settings.soft_spread_max_penalty,
    )
    ratio_penalty = 0
    if spread_ratio is not None:
        ratio_penalty = _linear_penalty(
            spread_ratio,
            settings.soft_spread_start_ratio,
            settings.hard_spread_max_ratio,
            settings.soft_spread_max_penalty,
        )
    penalty = max(points_penalty, ratio_penalty)

    return SpreadEvaluation(
        spread_points=spread_points,
        sl_points=sl_points,
        spread_ratio=spread_ratio,
        points_penalty=points_penalty,
        ratio_penalty=ratio_penalty,
        penalty=penalty,
    )


def is_hard_spread_block(eval_result: SpreadEvaluation) -> Tuple[bool, str]:
    settings = get_settings()
    if eval_result.spread_points >= settings.hard_spread_max_points:
        return True, "Spread trop élevé (points)"
    if eval_result.spread_ratio is not None and eval_result.spread_ratio > settings.hard_spread_max_ratio:
        return True, "Spread trop élevé (ratio/SL)"
    return False, ""
