"""
Moteur Fibonacci — bonus score uniquement (jamais pénalité).
Renforce les setups dont l'entrée est proche d'un niveau Fibonacci (38.2%, 50%, 61.8%).
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

log = logging.getLogger(__name__)

FIBO_LEVELS = (0.382, 0.5, 0.618)


def evaluate_fibo(
    entry_price: float,
    direction: str,
    swing_low: Optional[float],
    swing_high: Optional[float],
    atr: float,
    zone_min: float = 0.382,
    zone_max: float = 0.618,
    tolerance_atr: float = 0.15,
) -> Tuple[bool, float]:
    """
    Vérifie si entry_price est proche d'un niveau Fibonacci du swing M15.
    BUY: niveaux = swing_low + range * 0.382, 0.5, 0.618 (zone de retracement)
    SELL: niveaux = swing_high - range * 0.382, 0.5, 0.618
    Retourne (fibo_signal, distance_min_pts).
    """
    if swing_low is None or swing_high is None or atr <= 0:
        return False, 9999.0
    rng = swing_high - swing_low
    if rng <= 0:
        return False, 9999.0

    if direction.upper() == "BUY":
        levels = [swing_low + rng * f for f in FIBO_LEVELS]
    else:
        levels = [swing_high - rng * f for f in FIBO_LEVELS]

    tolerance_pts = tolerance_atr * atr
    dist_min = 9999.0
    for lvl in levels:
        d = abs(entry_price - lvl)
        if d < dist_min:
            dist_min = d
    fibo_signal = dist_min <= tolerance_pts

    # Vérifier aussi si entry est dans la zone [zone_min, zone_max] du range
    if direction.upper() == "BUY":
        pb_ratio = (entry_price - swing_low) / rng if rng > 0 else 0
    else:
        pb_ratio = (swing_high - entry_price) / rng if rng > 0 else 0
    in_zone = zone_min <= pb_ratio <= zone_max
    if in_zone and not fibo_signal:
        # Entry dans zone fibo même si pas exactement sur un niveau
        fibo_signal = True
        dist_min = 0.0

    if fibo_signal:
        log.info(
            "FIBO: swing_low=%.1f swing_high=%.1f entry=%.1f direction=%s dist_min=%.1f bonus_applied=%s",
            swing_low, swing_high, entry_price, direction, dist_min, fibo_signal,
        )
    return fibo_signal, dist_min
