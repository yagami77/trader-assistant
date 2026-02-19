"""Tests unitaires pour Room to Target engine."""
import pytest

from app.engines.room_to_target_engine import evaluate_room_to_target, RoomToTargetResult


def test_buy_ok_when_no_resistance():
    """BUY sans résistance au-dessus => OK."""
    r = evaluate_room_to_target(
        direction="BUY",
        entry_price=2650.0,
        tp1_price=2665.0,
        sr_levels=[2620.0, 2630.0],  # tous en-dessous
        atr_pts=20.0,
        mult=1.3,
    )
    assert r.ok
    assert r.room_pts >= 999


def test_buy_blocked_when_room_insufficient():
    """BUY avec résistance proche de TP1 => bloqué si room < tp1_pts * mult."""
    # tp1_distance = 15, required = 15 * 1.3 = 19.5
    # next_resistance = 2662 => room = 2662 - 2650 - 2 = 10 < 19.5
    r = evaluate_room_to_target(
        direction="BUY",
        entry_price=2650.0,
        tp1_price=2665.0,
        sr_levels=[2620.0, 2662.0],
        atr_pts=20.0,
        mult=1.3,
        buffer_pts=2.0,
    )
    assert not r.ok
    assert r.next_level == 2662.0
    assert r.room_pts < r.tp1_distance_pts * r.mult


def test_buy_ok_when_room_sufficient():
    """BUY avec résistance loin => OK."""
    r = evaluate_room_to_target(
        direction="BUY",
        entry_price=2650.0,
        tp1_price=2665.0,
        sr_levels=[2620.0, 2700.0],  # résistance bien au-dessus
        atr_pts=20.0,
        mult=1.3,
    )
    assert r.ok
    assert r.room_pts >= r.tp1_distance_pts * r.mult


def test_sell_ok_when_no_support():
    """SELL sans support en-dessous => OK."""
    r = evaluate_room_to_target(
        direction="SELL",
        entry_price=2650.0,
        tp1_price=2635.0,
        sr_levels=[2670.0, 2680.0],
        atr_pts=20.0,
    )
    assert r.ok
    assert r.room_pts >= 999


def test_sell_blocked_when_room_insufficient():
    """SELL avec support proche de TP1 => bloqué."""
    r = evaluate_room_to_target(
        direction="SELL",
        entry_price=2650.0,
        tp1_price=2635.0,
        sr_levels=[2638.0, 2670.0],  # support à 2638, tp1 à 2635
        atr_pts=20.0,
        mult=1.3,
        buffer_pts=2.0,
    )
    assert not r.ok
    assert r.next_level == 2638.0
