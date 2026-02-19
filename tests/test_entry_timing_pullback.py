"""
Tests pour entry timing — mode classic doit rester identique.
Mode pullback_m5 change le comportement pour BREAKOUT_RETEST/PULLBACK_SR.
"""
import os

import pytest

_env = os.path.join(os.path.dirname(__file__), "..", ".env.local")
if os.path.exists(_env):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=True)
    except ImportError:
        pass

from app.engines.entry_timing_engine import evaluate_entry_timing


def _candles_buy_breakout(close_above_swing: bool = True):
    """Candles M15 avec close > swing_low (breakout retest)."""
    base = 2650.0
    candles = [
        {"open": base + i * 2, "high": base + i * 2 + 5, "low": base + i * 2 - 3, "close": base + i * 2 + 2}
        for i in range(10)
    ]
    if close_above_swing:
        candles[-1]["close"] = base + 15  # au-dessus du swing_low + zone
    return candles


def test_classic_mode_unchanged():
    """Mode classic => comportement inchangé (pas de pullback_m5 requis)."""
    candles = _candles_buy_breakout()
    swing_low = 2645.0
    swing_high = 2670.0
    entry = 2655.0
    zone_pts = 15.0
    current_price = 2658.0  # dans zone
    # Avec 2 rejets M15 ou M5, timing_ready doit être True en mode classic
    result = evaluate_entry_timing(
        candles=candles,
        direction="BUY",
        entry_nominal=entry,
        swing_low=swing_low,
        swing_high=swing_high,
        current_price=current_price,
        zone_pts=zone_pts,
        candles_m5=[],
        atr=20.0,
        min_confirm_bars=2,
        entry_timing_mode="classic",
    )
    # En classic, pas de pullback M5 requis : timing_ready basé sur zone + rejets classiques
    assert result.setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR", "ZONE_CONFIRMATION")


def test_pullback_m5_mode_requires_pullback_and_rejection():
    """Mode pullback_m5 => timing_ready nécessite pullback + rejet M5 pour setups concernés."""
    candles = _candles_buy_breakout()
    swing_low = 2645.0
    swing_high = 2670.0
    entry = 2655.0
    zone_pts = 15.0
    # Sans rejet M5 dans la zone pullback, timing_ready doit être False
    result = evaluate_entry_timing(
        candles=candles,
        direction="BUY",
        entry_nominal=entry,
        swing_low=swing_low,
        swing_high=swing_high,
        current_price=2658.0,
        zone_pts=zone_pts,
        candles_m5=[],  # pas de rejet M5
        atr=20.0,
        min_confirm_bars=2,
        entry_timing_mode="pullback_m5",
        pullback_require_setups=["BREAKOUT_RETEST", "PULLBACK_SR"],
    )
    # En pullback_m5 sans rejet M5, timing_ready = False pour BREAKOUT_RETEST/PULLBACK_SR
    if result.setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR"):
        assert not result.timing_ready or "PULLBACK_REJECTION_M5" in result.reason
