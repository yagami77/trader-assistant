"""
Room to Target — éviter d'entrer quand TP1 est "collé" à une résistance/support.
Hard rule optionnelle activable par ROOM_TO_TARGET_ENABLED.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoomToTargetResult:
    ok: bool
    room_pts: float
    next_level: Optional[float]
    tp1_distance_pts: float
    mult: float
    reason: str


def evaluate_room_to_target(
    direction: str,
    entry_price: float,
    tp1_price: float,
    sr_levels: List[float],
    atr_pts: float,
    mult: float = 1.3,
    buffer_pts: float = 2.0,
) -> RoomToTargetResult:
    """
    Vérifie qu'il y a assez de "room" jusqu'au prochain niveau S/R pour atteindre TP1.
    BUY: next_resistance = plus proche SR au-dessus de entry
    SELL: next_support = plus proche SR en-dessous de entry
    Condition: room_pts >= tp1_distance_pts * mult
    """
    dir_upper = (direction or "BUY").upper()
    tp1_pts = abs(tp1_price - entry_price)
    if tp1_pts < 0.01:
        return RoomToTargetResult(
            ok=True,
            room_pts=999.0,
            next_level=None,
            tp1_distance_pts=tp1_pts,
            mult=mult,
            reason="TP1 distance nulle",
        )

    next_level: Optional[float] = None
    if dir_upper == "BUY":
        above = [l for l in sr_levels if l > entry_price + buffer_pts]
        next_level = min(above) if above else None
        if next_level is None:
            return RoomToTargetResult(
                ok=True,
                room_pts=999.0,
                next_level=None,
                tp1_distance_pts=tp1_pts,
                mult=mult,
                reason="Pas de résistance au-dessus",
            )
        room_pts = next_level - entry_price - buffer_pts
    else:
        below = [l for l in sr_levels if l < entry_price - buffer_pts]
        next_level = max(below) if below else None
        if next_level is None:
            return RoomToTargetResult(
                ok=True,
                room_pts=999.0,
                next_level=None,
                tp1_distance_pts=tp1_pts,
                mult=mult,
                reason="Pas de support en-dessous",
            )
        room_pts = entry_price - next_level - buffer_pts

    required = tp1_pts * mult
    ok = room_pts >= required
    reason = (
        f"Room OK: {room_pts:.1f} >= {required:.1f} (tp1={tp1_pts:.1f} * {mult})"
        if ok
        else f"Room insuffisant: {room_pts:.1f} < {required:.1f} (next_level={next_level:.2f})"
    )
    if not ok:
        log.info(
            "ROOM_TO_TARGET: entry=%.2f tp1=%.2f next_level=%s room_pts=%.1f tp1_pts=%.1f mult=%.2f -> %s",
            entry_price, tp1_price, next_level, room_pts, tp1_pts, mult, reason,
        )
    return RoomToTargetResult(
        ok=ok,
        room_pts=room_pts,
        next_level=next_level,
        tp1_distance_pts=tp1_pts,
        mult=mult,
        reason=reason,
    )
