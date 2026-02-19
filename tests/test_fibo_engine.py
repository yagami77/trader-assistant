"""Tests unitaires pour Fibonacci engine (bonus score)."""
import pytest

from app.engines.fibo_engine import evaluate_fibo, FIBO_LEVELS


def test_fibo_buy_entry_near_382():
    """BUY avec entry proche du 38.2% => fibo_signal True."""
    swing_low, swing_high = 2640.0, 2680.0
    range_ = swing_high - swing_low
    level_382 = swing_low + range_ * 0.382
    atr = 20.0
    signal, dist = evaluate_fibo(
        entry_price=level_382,
        direction="BUY",
        swing_low=swing_low,
        swing_high=swing_high,
        atr=atr,
        tolerance_atr=0.15,
    )
    assert signal
    assert dist <= 0.15 * atr


def test_fibo_buy_entry_far_from_levels():
    """BUY avec entry loin des niveaux fibo => fibo_signal False."""
    swing_low, swing_high = 2640.0, 2680.0
    entry = 2675.0  # proche du high, loin des retracements
    atr = 20.0
    signal, _ = evaluate_fibo(
        entry_price=entry,
        direction="BUY",
        swing_low=swing_low,
        swing_high=swing_high,
        atr=atr,
        tolerance_atr=0.15,
    )
    assert not signal


def test_fibo_sell_entry_in_zone():
    """SELL avec entry dans zone fibo (retracement) => fibo_signal True."""
    swing_low, swing_high = 2640.0, 2680.0
    # Zone fibo SELL = swing_high - range * [0.382, 0.618]
    # 2680 - 40*0.5 = 2660
    entry = 2660.0
    atr = 20.0
    signal, _ = evaluate_fibo(
        entry_price=entry,
        direction="SELL",
        swing_low=swing_low,
        swing_high=swing_high,
        atr=atr,
        zone_min=0.382,
        zone_max=0.618,
    )
    assert signal


def test_fibo_no_swing_returns_false():
    """Sans swing_low ou swing_high => False."""
    signal, _ = evaluate_fibo(
        entry_price=2650.0,
        direction="BUY",
        swing_low=None,
        swing_high=2680.0,
        atr=20.0,
    )
    assert not signal
