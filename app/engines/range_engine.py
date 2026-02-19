"""
Indicateurs pour le mode Range Strategy (H1 RANGE).
Alimente le state avec: range_rejet_borne, range_sweep, range_break_structure, range_volume_spike.
"""
from __future__ import annotations

from typing import List, Optional


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


def evaluate_range_indicators(
    candles_m15: List[dict],
    direction: str,
    entry: float,
    last_swing_low: Optional[float],
    last_swing_high: Optional[float],
    atr: float,
    timing_ready: bool,
    setup_type: str,
    candles_m5: Optional[List[dict]] = None,
) -> dict:
    """
    Calcule les 4 indicateurs range pour le scoring Mode RANGE.
    Retourne un dict avec: range_rejet_borne, range_sweep, range_break_structure, range_volume_spike (bool).
    """
    out = {
        "range_rejet_borne": False,
        "range_sweep": False,
        "range_break_structure": False,
        "range_volume_spike": False,
    }
    if not candles_m15 or len(candles_m15) < 6:
        return out

    highs = _extract_series(candles_m15, "high")
    lows = _extract_series(candles_m15, "low")
    closes = _extract_series(candles_m15, "close")
    if len(highs) < 6 or len(lows) < 6 or len(closes) < 6:
        return out

    atr_tol = max(2.0, atr * 0.35) if atr and atr > 0 else 5.0

    # --- Rejet borne extrême : entrée proche de la borne (S/R extrême) + setup pullback/breakout ---
    if last_swing_low is not None and last_swing_high is not None:
        if direction == "BUY":
            dist_to_bound = abs(entry - last_swing_low)
            near_bound = dist_to_bound <= atr_tol
        else:
            dist_to_bound = abs(entry - last_swing_high)
            near_bound = dist_to_bound <= atr_tol
        setup_ok = setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR") or timing_ready
        out["range_rejet_borne"] = bool(near_bound and setup_ok)

    # --- Sweep high/low : une barre récente a dépassé le swing puis refermé dedans (liquidity grab) ---
    lookback = min(6, len(highs) - 1)
    for i in range(-lookback, 0):
        idx = len(highs) + i
        if idx < 0:
            continue
        h, l, c = highs[idx], lows[idx], closes[idx]
        if direction == "SELL" and last_swing_high is not None:
            # Sweep du high : high > niveau, close < niveau
            if h > last_swing_high + (atr * 0.1) and c < last_swing_high:
                out["range_sweep"] = True
                break
        if direction == "BUY" and last_swing_low is not None:
            if l < last_swing_low - (atr * 0.1) and c > last_swing_low:
                out["range_sweep"] = True
                break

    # --- Break structure interne : type breakout/retest ou cassure d'un niveau interne récent ---
    if setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR"):
        out["range_break_structure"] = True
    else:
        # Fallback : sur M15, dernier swing a été cassé puis prix revenu (dernières barres)
        n = len(closes)
        if n >= 10 and last_swing_low is not None and last_swing_high is not None:
            recent_high = max(highs[-5:]) if len(highs) >= 5 else None
            recent_low = min(lows[-5:]) if len(lows) >= 5 else None
            last_c = closes[-1]
            if direction == "BUY" and recent_low is not None:
                # Prix est remonté après avoir cassé sous un niveau récent
                if recent_low < last_swing_low and last_c > last_swing_low:
                    out["range_break_structure"] = True
            if direction == "SELL" and recent_high is not None:
                if recent_high > last_swing_high and last_c < last_swing_high:
                    out["range_break_structure"] = True

    # --- Volume spike : dernier bar volume > 1.4 x moyenne(20) si volume dispo ---
    vols = _extract_series(candles_m15, "volume")
    if not vols:
        vols = _extract_series(candles_m15, "tick_volume")
    if len(vols) >= 5:
        last_vol = vols[-1]
        avg_vol = sum(vols[-21:-1]) / 20 if len(vols) >= 21 else (sum(vols[:-1]) / (len(vols) - 1) if len(vols) > 1 else last_vol)
        if avg_vol and avg_vol > 0 and last_vol >= 1.4 * avg_vol:
            out["range_volume_spike"] = True

    return out
