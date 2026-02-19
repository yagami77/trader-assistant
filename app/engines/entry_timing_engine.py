"""
Moteur de timing d'entrée — style pro.
Entre au BON moment: zone d'entrée + confirmation (rejet, breakout), pas juste à la clôture.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EntryTimingResult:
    setup_type: str  # "BREAKOUT_RETEST" | "PULLBACK_SR" | "ZONE_CONFIRMATION"
    entry_zone_lo: float
    entry_zone_hi: float
    timing_ready: bool  # bon moment maintenant ?
    reason: str
    confirmation_bars: int  # nb barres de confirmation
    # Détails des étapes (pullback_m5) : pour affichage "Bon moment" avec ✓/⏳
    timing_step_zone_ok: Optional[bool] = None
    timing_step_pullback_ok: Optional[bool] = None
    timing_step_m5_ok: Optional[bool] = None


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


def _m5_rejection_count(candles_m5: List[dict], direction: str) -> int:
    """Nombre de barres M5 (dernières 3) qui sont des rejets dans notre direction."""
    if not candles_m5:
        return 0
    last_3 = candles_m5[-3:] if len(candles_m5) >= 3 else candles_m5
    count = 0
    for c in last_3:
        if direction.upper() == "BUY" and _is_rejection_candle_bullish(c):
            count += 1
        elif direction.upper() == "SELL" and _is_rejection_candle_bearish(c):
            count += 1
    return count


def _find_impulse_candle(candles: List[dict], direction: str, atr: float = 20.0) -> Optional[tuple]:
    """Bougie impulsive M15 (range max parmi les dernières). Retourne (impulse_low, impulse_high, impulse_range)."""
    if not candles or len(candles) < 3:
        return None
    lookback = min(8, len(candles))
    best = None
    best_range = 0.0
    for i in range(-lookback, 0):
        c = candles[i]
        h = float(c.get("high", 0) or 0)
        l = float(c.get("low", 0) or 0)
        rng = h - l
        if rng >= atr * 0.3 and rng > best_range:
            best_range = rng
            best = (l, h, rng)
    return best


def _pullback_zone(impulse: tuple, direction: str, min_ratio: float, max_ratio: float) -> tuple:
    """Zone pullback (pb_min, pb_max). BUY: bas 30-50%, SELL: haut 30-50%."""
    lo, hi, rng = impulse
    if direction.upper() == "BUY":
        pb_min = lo + rng * min_ratio
        pb_max = lo + rng * max_ratio
    else:
        pb_min = hi - rng * max_ratio
        pb_max = hi - rng * min_ratio
    return (pb_min, pb_max)


def _m5_rejection_in_pullback_zone(
    candles_m5: List[dict],
    direction: str,
    pb_min: float,
    pb_max: float,
    lookback: int = 6,
) -> bool:
    """
    Au moins 1 M5 récente a: low touché sous pb_min (BUY) ou high touché au-dessus pb_max (SELL),
    ET close dans la zone (rejet).
    """
    if not candles_m5:
        return False
    bars = candles_m5[-lookback:] if len(candles_m5) >= lookback else candles_m5
    for c in bars:
        l = float(c.get("low", 0) or 0)
        h = float(c.get("high", 0) or 0)
        close = float(c.get("close", 0) or 0)
        if direction.upper() == "BUY":
            if l <= pb_min + 2.0 and close >= pb_min and close <= pb_max:
                return True
        else:
            if h >= pb_max - 2.0 and close <= pb_max and close >= pb_min:
                return True
    return False


def evaluate_entry_timing(
    candles: List[dict],
    direction: str,
    entry_nominal: float,
    swing_low: Optional[float],
    swing_high: Optional[float],
    current_price: Optional[float],
    zone_pts: Optional[float] = None,
    candles_m5: Optional[List[dict]] = None,
    atr: Optional[float] = None,
    min_confirm_bars: int = 2,
    entry_timing_mode: str = "classic",
    pullback_min_ratio: float = 0.30,
    pullback_max_ratio: float = 0.50,
    pullback_require_setups: Optional[List[str]] = None,
    m5_rejection_lookback: int = 6,
) -> EntryTimingResult:
    """
    Setup M15, confirmation : 2 rejets M15 ou 2 barres M5 rejet.
    - Zone d'entrée : ATR * mult (ou zone_pts si fourni)
    - current_price requis pour valider entrée (prix dans zone au tick)
    """
    if zone_pts is None and atr is not None:
        from app.config import get_settings
        s = get_settings()
        mult = getattr(s, "entry_zone_atr_mult", 0.35)
        z_min = getattr(s, "entry_zone_min_pts", 8.0)
        z_max = getattr(s, "entry_zone_max_pts", 25.0)
        zone_pts = max(z_min, min(z_max, atr * mult))
    if zone_pts is None:
        zone_pts = 15.0

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
    # Prix de référence : tick obligatoire pour valider l'entrée (pas seulement close M15)
    price_ref = current_price if current_price is not None else close
    in_zone = _price_in_zone(price_ref, zone_lo, zone_hi)
    last_3 = candles[-3:] if len(candles) >= 3 else candles
    confirmation_count = 0
    setup_type = "ZONE_CONFIRMATION"
    reason = "En attente de confirmation"
    step_zone, step_pb, step_m5 = None, None, None
    if direction == "BUY":
        if swing_low is not None and close > swing_low + zone_pts:
            setup_type = "BREAKOUT_RETEST"
            for c in last_3:
                if _is_rejection_candle_bullish(c):
                    confirmation_count += 1
            m5_count = _m5_rejection_count(candles_m5 or [], direction)
            has_confirm = confirmation_count >= min_confirm_bars or m5_count >= min_confirm_bars
            timing_ready = in_zone and has_confirm
            if entry_timing_mode == "pullback_m5" and setup_type in (pullback_require_setups or ["BREAKOUT_RETEST", "PULLBACK_SR"]):
                impulse = _find_impulse_candle(candles, direction, atr or 20.0)
                if impulse and (price_ref := (current_price if current_price is not None else close)):
                    pb_min, pb_max = _pullback_zone(impulse, direction, pullback_min_ratio, pullback_max_ratio)
                    in_pb = _price_in_zone(price_ref, pb_min, pb_max)
                    m5_rej = _m5_rejection_in_pullback_zone(candles_m5 or [], direction, pb_min, pb_max, m5_rejection_lookback)
                    step_zone, step_pb, step_m5 = in_zone, in_pb, m5_rej
                    if in_pb and m5_rej:
                        timing_ready = True
                        reason = f"PULLBACK_REJECTION_M5 zone=[{pb_min:.1f},{pb_max:.1f}]"
                    elif not in_pb or not m5_rej:
                        timing_ready = False
                        reason = "Pullback M5 - en attente zone + rejet" if in_zone else "En attente du pullback"
                else:
                    step_zone, step_pb, step_m5 = in_zone, False, False
            elif timing_ready:
                reason = f"Pullback + rejet x{confirmation_count}" + (f" / M5 x{m5_count}" if m5_count else "")
            else:
                reason = "Breakout retest - en attente rejets" if in_zone else "En attente du pullback"
        else:
            for c in last_3:
                if _is_rejection_candle_bullish(c):
                    confirmation_count += 1
            m5_count = _m5_rejection_count(candles_m5 or [], direction)
            has_confirm = confirmation_count >= min_confirm_bars or m5_count >= min_confirm_bars
            timing_ready = in_zone and has_confirm
            setup_type = "PULLBACK_SR"
            if entry_timing_mode == "pullback_m5" and setup_type in (pullback_require_setups or ["BREAKOUT_RETEST", "PULLBACK_SR"]):
                impulse = _find_impulse_candle(candles, direction, atr or 20.0)
                if impulse and (price_ref := (current_price if current_price is not None else close)):
                    pb_min, pb_max = _pullback_zone(impulse, direction, pullback_min_ratio, pullback_max_ratio)
                    in_pb = _price_in_zone(price_ref, pb_min, pb_max)
                    m5_rej = _m5_rejection_in_pullback_zone(candles_m5 or [], direction, pb_min, pb_max, m5_rejection_lookback)
                    timing_ready = in_zone and in_pb and m5_rej
                    reason = f"PULLBACK_REJECTION_M5" if timing_ready else f"Rejet S/R x{confirmation_count} - attente pullback M5"
                    log.info(
                        "PULLBACK BUY PULLBACK_SR: impulse_range=%.1f pb_min=%.1f pb_max=%.1f current_price=%.1f m5_rejection=%s",
                        impulse[2], pb_min, pb_max, price_ref, m5_rej,
                    )
                else:
                    timing_ready = False
                    reason = "Pullback M5 - impulsion non trouvée"
            else:
                reason = f"Rejet S/R x{confirmation_count}" + (f" / M5 x{m5_count}" if m5_count else "")
    else:
        if swing_high is not None and close < swing_high - zone_pts:
            setup_type = "BREAKOUT_RETEST"
            for c in last_3:
                if _is_rejection_candle_bearish(c):
                    confirmation_count += 1
            m5_count = _m5_rejection_count(candles_m5 or [], direction)
            has_confirm = confirmation_count >= min_confirm_bars or m5_count >= min_confirm_bars
            timing_ready = in_zone and has_confirm
            if entry_timing_mode == "pullback_m5" and setup_type in (pullback_require_setups or ["BREAKOUT_RETEST", "PULLBACK_SR"]):
                impulse = _find_impulse_candle(candles, direction, atr or 20.0)
                if impulse and (price_ref := (current_price if current_price is not None else close)):
                    pb_min, pb_max = _pullback_zone(impulse, direction, pullback_min_ratio, pullback_max_ratio)
                    in_pb = _price_in_zone(price_ref, pb_min, pb_max)
                    m5_rej = _m5_rejection_in_pullback_zone(candles_m5 or [], direction, pb_min, pb_max, m5_rejection_lookback)
                    step_zone, step_pb, step_m5 = in_zone, in_pb, m5_rej
                    timing_ready = in_pb and m5_rej
                    reason = f"PULLBACK_REJECTION_M5 zone=[{pb_min:.1f},{pb_max:.1f}]" if timing_ready else "Pullback M5 - en attente zone + rejet"
                    log.info(
                        "PULLBACK SELL BREAKOUT: impulse_range=%.1f pb_min=%.1f pb_max=%.1f current_price=%.1f m5_rejection=%s",
                        impulse[2], pb_min, pb_max, price_ref, m5_rej,
                    )
                else:
                    timing_ready = False
                    step_zone, step_pb, step_m5 = in_zone, False, False
                    reason = "Pullback M5 - impulsion non trouvée"
            elif timing_ready:
                reason = f"Pullback + rejet x{confirmation_count}" + (f" / M5 x{m5_count}" if m5_count else "")
            else:
                reason = "Breakout retest - en attente rejets" if in_zone else "En attente du pullback"
        else:
            for c in last_3:
                if _is_rejection_candle_bearish(c):
                    confirmation_count += 1
            m5_count = _m5_rejection_count(candles_m5 or [], direction)
            has_confirm = confirmation_count >= min_confirm_bars or m5_count >= min_confirm_bars
            timing_ready = in_zone and has_confirm
            setup_type = "PULLBACK_SR"
            if entry_timing_mode == "pullback_m5" and setup_type in (pullback_require_setups or ["BREAKOUT_RETEST", "PULLBACK_SR"]):
                impulse = _find_impulse_candle(candles, direction, atr or 20.0)
                if impulse and (price_ref := (current_price if current_price is not None else close)):
                    pb_min, pb_max = _pullback_zone(impulse, direction, pullback_min_ratio, pullback_max_ratio)
                    in_pb = _price_in_zone(price_ref, pb_min, pb_max)
                    m5_rej = _m5_rejection_in_pullback_zone(candles_m5 or [], direction, pb_min, pb_max, m5_rejection_lookback)
                    timing_ready = in_zone and in_pb and m5_rej
                    reason = f"PULLBACK_REJECTION_M5" if timing_ready else f"Rejet S/R x{confirmation_count} - attente pullback M5"
                    log.info(
                        "PULLBACK SELL PULLBACK_SR: impulse_range=%.1f pb_min=%.1f pb_max=%.1f current_price=%.1f m5_rejection=%s",
                        impulse[2], pb_min, pb_max, price_ref, m5_rej,
                    )
                else:
                    timing_ready = False
                    reason = "Pullback M5 - impulsion non trouvée"
            else:
                reason = f"Rejet S/R x{confirmation_count}" + (f" / M5 x{m5_count}" if m5_count else "")
    return EntryTimingResult(
        setup_type=setup_type,
        entry_zone_lo=zone_lo,
        entry_zone_hi=zone_hi,
        timing_ready=timing_ready,
        reason=reason,
        confirmation_bars=confirmation_count,
        timing_step_zone_ok=step_zone,
        timing_step_pullback_ok=step_pb,
        timing_step_m5_ok=step_m5,
    )
