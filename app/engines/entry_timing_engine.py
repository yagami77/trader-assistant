"""
Moteur de timing d'entrée — style pro.
Entre au BON moment: zone d'entrée + confirmation (rejet, breakout), pas juste à la clôture.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class EntryTimingResult:
    setup_type: str  # "BREAKOUT_RETEST" | "PULLBACK_SR" | "ZONE_CONFIRMATION"
    entry_zone_lo: float
    entry_zone_hi: float
    timing_ready: bool  # bon moment maintenant ?
    reason: str
    confirmation_bars: int  # nb barres de confirmation


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


def _is_rejection_candle_bullish(candle: dict) -> bool:
    """Mèche basse longue = rejet haussier (acheteurs ont repoussé)."""
    o, h, l, c = (
        float(candle.get("open", 0)),
        float(candle.get("high", 0)),
        float(candle.get("low", 0)),
        float(candle.get("close", 0)),
    )
    body = abs(c - o)
    lower_wick = min(o, c) - l
    total = h - l
    if total <= 0:
        return False
    return lower_wick > body * 1.5 and lower_wick > total * 0.4


def _is_rejection_candle_bearish(candle: dict) -> bool:
    """Mèche haute longue = rejet baissier."""
    o, h, l, c = (
        float(candle.get("open", 0)),
        float(candle.get("high", 0)),
        float(candle.get("low", 0)),
        float(candle.get("close", 0)),
    )
    body = abs(c - o)
    upper_wick = h - max(o, c)
    total = h - l
    if total <= 0:
        return False
    return upper_wick > body * 1.5 and upper_wick > total * 0.4


def _price_in_zone(price: float, zone_lo: float, zone_hi: float) -> bool:
    return zone_lo <= price <= zone_hi


def get_m5_trend(candles_m5: List[dict], direction: str, min_bars: int = 3) -> str:
    """Retourne 'aligned' | 'against' | 'neutral' selon la tendance M5 vs direction."""
    if not candles_m5 or len(candles_m5) < min_bars:
        return "neutral"
    closes = _extract_series(candles_m5, "close")
    if len(closes) < min_bars:
        return "neutral"
    recent = closes[-min_bars:]
    older = closes[-min_bars * 2 : -min_bars] if len(closes) >= min_bars * 2 else closes[:min_bars]
    if not older:
        return "neutral"
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    diff = avg_recent - avg_older
    if direction.upper() == "BUY":
        if diff < -2.0:
            return "against"
        if diff > 2.0:
            return "aligned"
    else:
        if diff > 2.0:
            return "against"
        if diff < -2.0:
            return "aligned"
    return "neutral"


def _m5_has_one_rejection(candles_m5: List[dict], direction: str) -> bool:
    """True si au moins 1 barre M5 (dernières 3) est un rejet dans notre direction."""
    if not candles_m5:
        return False
    last_3 = candles_m5[-3:] if len(candles_m5) >= 3 else candles_m5
    for c in last_3:
        if direction.upper() == "BUY" and _is_rejection_candle_bullish(c):
            return True
        if direction.upper() == "SELL" and _is_rejection_candle_bearish(c):
            return True
    return False


def evaluate_entry_timing(
    candles: List[dict],
    direction: str,
    entry_nominal: float,
    swing_low: Optional[float],
    swing_high: Optional[float],
    current_price: Optional[float],
    zone_pts: float = 15.0,
    candles_m5: Optional[List[dict]] = None,
) -> EntryTimingResult:
    """
    Setup M15, confirmation M5 : 1 barre M5 rejet valide suffit.
    - Zone d'entrée autour du niveau (M15)
    - Confirmation: rejet M15 ou 1 barre M5 rejet dans notre direction
    - current_price optionnel (tick) pour savoir si on est DANS la zone
    """
    if not candles:
        return EntryTimingResult(
            setup_type="ZONE_CONFIRMATION",
            entry_zone_lo=entry_nominal - zone_pts,
            entry_zone_hi=entry_nominal + zone_pts,
            timing_ready=False,
            reason="Pas de données",
            confirmation_bars=0,
        )
    last = candles[-1]
    close = float(last.get("close", entry_nominal))
    zone_lo = entry_nominal - zone_pts
    zone_hi = entry_nominal + zone_pts
    price_ref = current_price if current_price is not None else close
    in_zone = _price_in_zone(price_ref, zone_lo, zone_hi)
    last_3 = candles[-3:] if len(candles) >= 3 else candles
    confirmation_count = 0
    setup_type = "ZONE_CONFIRMATION"
    reason = "En attente de confirmation"
    if direction == "BUY":
        if swing_low is not None and close > swing_low + zone_pts:
            setup_type = "BREAKOUT_RETEST"
            if in_zone:
                for c in last_3:
                    if _is_rejection_candle_bullish(c):
                        confirmation_count += 1
                if confirmation_count >= 1:
                    timing_ready = True
                    reason = "Pullback + rejet haussier"
                elif in_zone:
                    timing_ready = True
                    reason = "Prix dans zone d'entrée"
                else:
                    timing_ready = False
            else:
                timing_ready = in_zone
                reason = "Breakout retest - prix dans zone" if in_zone else "En attente du pullback"
        else:
            for c in last_3:
                if _is_rejection_candle_bullish(c):
                    confirmation_count += 1
            timing_ready = in_zone and (confirmation_count >= 1 or close > zone_lo)
            setup_type = "PULLBACK_SR"
            reason = (
                f"Rejet S/R x{confirmation_count}" if confirmation_count else "Prix dans zone"
            )
    else:
        if swing_high is not None and close < swing_high - zone_pts:
            setup_type = "BREAKOUT_RETEST"
            if in_zone:
                for c in last_3:
                    if _is_rejection_candle_bearish(c):
                        confirmation_count += 1
                if confirmation_count >= 1:
                    timing_ready = True
                    reason = "Pullback + rejet baissier"
                elif in_zone:
                    timing_ready = True
                    reason = "Prix dans zone d'entrée"
                else:
                    timing_ready = False
            else:
                timing_ready = in_zone
                reason = "Breakout retest - prix dans zone" if in_zone else "En attente du pullback"
        else:
            for c in last_3:
                if _is_rejection_candle_bearish(c):
                    confirmation_count += 1
            timing_ready = in_zone and (confirmation_count >= 1 or close < zone_hi)
            setup_type = "PULLBACK_SR"
            reason = (
                f"Rejet S/R x{confirmation_count}" if confirmation_count else "Prix dans zone"
            )
    # Confirmation M5 : 1 barre M5 rejet dans notre direction suffit (pas d'attente 2 M15)
    if not timing_ready and candles_m5 and _m5_has_one_rejection(candles_m5, direction):
        timing_ready = True
        reason = f"{reason} — Confirmation M5 (1 barre)"
    return EntryTimingResult(
        setup_type=setup_type,
        entry_zone_lo=zone_lo,
        entry_zone_hi=zone_hi,
        timing_ready=timing_ready,
        reason=reason,
        confirmation_bars=confirmation_count,
    )
