"""Tests pour le Break-even automatique après TP1."""
import os

import pytest

from app.engines.suivi_engine import evaluate_suivi
from app.infra.db import (
    get_conn,
    init_db,
    get_active_trade,
    set_active_trade,
    update_active_trade_sl_to_be,
    clear_active_trade,
)


def _p(tmp_path):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test_be.db")
    for k in ["BE_ENABLED", "BE_OFFSET_PTS"]:
        os.environ.pop(k, None)
    from app.config import get_settings
    get_settings.cache_clear()
    init_db()


def test_evaluate_suivi_tp1_be_message_format():
    """Message TP1+BE contient les infos attendues (Bravo, BE, entrée, SL, TP2, pts)."""
    result = evaluate_suivi(
        current_price=5035.0,
        direction="BUY",
        entry=5027.0,
        sl=5012.0,
        tp1=5032.0,
        tp2=5045.0,
        structure_h1="BULLISH",
        candles_m15=[],
        be_enabled=True,
        be_applied=False,
    )
    msg = result.message
    assert "Bravo" in msg and "TP1 atteint" in msg
    assert "Break-even" in msg
    assert "5027.00" in msg
    assert "5045.00" in msg
    assert "+5" in msg or "+5.0" in msg
    assert "TP2" in msg


def test_evaluate_suivi_tp1_be_when_enabled():
    """TP1 atteint + BE activé + be_applied=False → TP1_BE (closed=False)."""
    result = evaluate_suivi(
        current_price=5035.0,  # >= tp1 pour BUY
        direction="BUY",
        entry=5027.0,
        sl=5012.0,
        tp1=5032.0,
        tp2=5045.0,
        structure_h1="BULLISH",
        candles_m15=[],
        be_enabled=True,
        be_applied=False,
    )
    assert result.status == "TP1_BE"
    assert result.closed is False
    assert "TP1 atteint" in result.message
    assert "Break-even" in result.message


def test_evaluate_suivi_tp1_sortie_when_be_disabled():
    """TP1 atteint + BE désactivé → SORTIE (comportement actuel)."""
    result = evaluate_suivi(
        current_price=5035.0,
        direction="BUY",
        entry=5027.0,
        sl=5012.0,
        tp1=5032.0,
        tp2=5045.0,
        structure_h1="BULLISH",
        candles_m15=[],
        be_enabled=False,
    )
    assert result.status == "SORTIE"
    assert result.closed is True
    assert result.outcome_pips == 5.0  # 5032 - 5027


def test_evaluate_suivi_tp1_be_sell():
    """TP1 atteint SELL + BE activé → TP1_BE."""
    result = evaluate_suivi(
        current_price=5015.0,  # <= tp1 pour SELL
        direction="SELL",
        entry=5027.0,
        sl=5042.0,
        tp1=5020.0,
        tp2=5005.0,
        structure_h1="BEARISH",
        candles_m15=[],
        be_enabled=True,
        be_applied=False,
    )
    assert result.status == "TP1_BE"
    assert result.closed is False


def test_update_active_trade_sl_to_be_buy(tmp_path):
    """BUY: SL devient entry + offset."""
    _p(tmp_path)
    day = "2026-02-02"
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO state (day_paris, daily_loss_amount, daily_budget_amount, consecutive_losses) VALUES (?, 0, 100, 0)",
        (day,),
    )
    conn.commit()
    conn.close()

    set_active_trade(day, entry=5027.0, sl=5012.0, tp1=5032.0, tp2=5045.0, direction="BUY", started_ts="2026-02-02T10:00:00Z")
    updated = update_active_trade_sl_to_be(day, 5027.0, "BUY", offset_pts=2.0)
    assert updated is True

    active = get_active_trade(day)
    assert active is not None
    assert float(active["active_sl"]) == 5029.0  # 5027 + 2
    assert active["active_be_applied"] == 1


def test_update_active_trade_sl_to_be_sell(tmp_path):
    """SELL: SL devient entry - offset."""
    _p(tmp_path)
    day = "2026-02-02"
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO state (day_paris, daily_loss_amount, daily_budget_amount, consecutive_losses) VALUES (?, 0, 100, 0)",
        (day,),
    )
    conn.commit()
    conn.close()

    set_active_trade(day, entry=5027.0, sl=5042.0, tp1=5020.0, tp2=5005.0, direction="SELL", started_ts="2026-02-02T10:00:00Z")
    updated = update_active_trade_sl_to_be(day, 5027.0, "SELL", offset_pts=1.5)
    assert updated is True

    active = get_active_trade(day)
    assert float(active["active_sl"]) == 5025.5  # 5027 - 1.5


def test_update_active_trade_sl_to_be_idempotent(tmp_path):
    """Rerun après BE appliqué → pas de nouvelle mise à jour."""
    _p(tmp_path)
    day = "2026-02-02"
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO state (day_paris, daily_loss_amount, daily_budget_amount, consecutive_losses) VALUES (?, 0, 100, 0)",
        (day,),
    )
    conn.commit()
    conn.close()

    set_active_trade(day, entry=5027.0, sl=5012.0, tp1=5032.0, tp2=5045.0, direction="BUY", started_ts="2026-02-02T10:00:00Z")
    updated1 = update_active_trade_sl_to_be(day, 5027.0, "BUY")
    updated2 = update_active_trade_sl_to_be(day, 5027.0, "BUY")
    assert updated1 is True
    assert updated2 is False
