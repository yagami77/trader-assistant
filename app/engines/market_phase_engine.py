"""
Moteur de phase marché — style pro.
Détecte: IMPULSE / PULLBACK / CONSOLIDATION / REVERSAL.
Renforce la décision sans modifier les règles existantes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.engines.structure_engine import analyze_structure, StructureResult


def _extract_series(candles: List[dict], key: str) -> List[float]:
    out: List[float] = []
    for c in candles:
        v = c.get(key)
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


@dataclass(frozen=True)
class MarketPhaseResult:
    phase: str  # IMPULSE | PULLBACK | CONSOLIDATION | REVERSAL
    reason: str


def get_market_phase(
    candles_m15: List[dict],
    candles_h1: Optional[List[dict]] = None,
    struct_m15: Optional[StructureResult] = None,
) -> MarketPhaseResult:
    """
    Détermine la phase de marché à partir de structure M15/H1.
    - IMPULSE: mouvement directionnel net (structure claire, range récent faible)
    - PULLBACK: retracement vers zone (prix revient vers swing/S/R)
    - CONSOLIDATION: range, pas de direction claire
    - REVERSAL: potentiel retournement (structure H1 vs M15 divergente ou momentum inverse)
    """
    if not candles_m15:
        return MarketPhaseResult("CONSOLIDATION", "Pas de données")

    struct = struct_m15 or analyze_structure(candles_m15)
    struct_h1 = analyze_structure(candles_h1) if candles_h1 else struct

    closes = _extract_series(candles_m15, "close")
    highs = _extract_series(candles_m15, "high")
    lows = _extract_series(candles_m15, "low")

    if len(closes) < 10:
        return MarketPhaseResult("CONSOLIDATION", "Historique insuffisant")

    last_close = closes[-1]
    recent_range = max(highs[-8:]) - min(lows[-8:]) if len(highs) >= 8 and len(lows) >= 8 else 0
    older_range = max(highs[-16:-8]) - min(lows[-16:-8]) if len(highs) >= 16 and len(lows) >= 16 else recent_range
    avg_range = (recent_range + older_range) / 2 if older_range > 0 else recent_range

    # Momentum court (4 barres) vs moyen (12 barres)
    mom_short = closes[-1] - closes[-5] if len(closes) >= 5 else 0
    mom_medium = closes[-1] - closes[-13] if len(closes) >= 13 else 0

    # Structure H1 vs M15 divergente = potentiel REVERSAL
    if struct_h1.structure != struct.structure:
        if (struct_h1.structure == "BULLISH" and struct.structure == "BEARISH") or (
            struct_h1.structure == "BEARISH" and struct.structure == "BULLISH"
        ):
            return MarketPhaseResult("REVERSAL", "Structure H1 vs M15 divergente")

    # Range très serré = CONSOLIDATION
    if avg_range > 0 and recent_range < avg_range * 0.5:
        return MarketPhaseResult("CONSOLIDATION", "Range serré")

    # Structure RANGE = CONSOLIDATION
    if struct.structure == "RANGE":
        return MarketPhaseResult("CONSOLIDATION", "Structure range")

    # Pullback: prix proche d'un niveau S/R ou swing (dans zone 0.3% du niveau)
    last_hl = struct.last_swing_low
    last_lh = struct.last_swing_high
    zone_pct = 0.003
    if struct.structure == "BULLISH" and last_hl is not None:
        dist_pct = abs(last_close - last_hl) / last_hl if last_hl else 1
        if dist_pct <= zone_pct and last_close >= last_hl - 10:
            return MarketPhaseResult("PULLBACK", "Prix proche swing low (pullback BUY)")
    if struct.structure == "BEARISH" and last_lh is not None:
        dist_pct = abs(last_close - last_lh) / last_lh if last_lh else 1
        if dist_pct <= zone_pct and last_close <= last_lh + 10:
            return MarketPhaseResult("PULLBACK", "Prix proche swing high (pullback SELL)")

    # Momentum aligné avec structure = IMPULSE
    if struct.structure == "BULLISH" and mom_short > 5 and mom_medium > 5:
        return MarketPhaseResult("IMPULSE", "Momentum haussier aligné")
    if struct.structure == "BEARISH" and mom_short < -5 and mom_medium < -5:
        return MarketPhaseResult("IMPULSE", "Momentum baissier aligné")

    # Par défaut: CONSOLIDATION si rien de net
    return MarketPhaseResult("CONSOLIDATION", "Phase indéterminée")
