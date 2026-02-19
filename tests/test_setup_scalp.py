"""
Tests unitaires pour le setup scalp XAUUSD M15.
TP1 clamp 10-20, SL clamp 20-40, TP2 bonus optionnel.
"""
import os

import pytest

# Charger .env.local pour les tests
_env = os.path.join(os.path.dirname(__file__), "..", ".env.local")
if os.path.exists(_env):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=True)
    except ImportError:
        pass


def test_tp1_clamped(monkeypatch):
    """TP1 doit être clampé dans [TP1_MIN_PTS, TP1_MAX_PTS]."""
    monkeypatch.setenv("TP1_MIN_PTS", "10")
    monkeypatch.setenv("TP1_MAX_PTS", "20")
    monkeypatch.setenv("SL_MIN_PTS", "20")
    monkeypatch.setenv("SL_MAX_PTS", "40")
    monkeypatch.setenv("RR_MIN_TP1", "0.4")
    # Invalider le cache settings
    from app.config import get_settings
    get_settings.cache_clear()

    from app.engines.setup_engine import detect_setups

    candles = [{"open": 4940, "high": 4945, "low": 4935, "close": 4942}] * 20
    result = detect_setups(candles)
    tp1_dist = abs(result.tp1 - result.entry)
    assert 10 <= tp1_dist <= 20, f"TP1 distance {tp1_dist} hors [10, 20]"
    get_settings.cache_clear()


def test_sl_too_large_blocks(monkeypatch):
    """SL > SL_MAX_PTS => NO_GO + blocked_by=SL_TOO_LARGE."""
    monkeypatch.setenv("SL_MAX_PTS", "40")
    monkeypatch.setenv("ENTRY_LIQUIDITY_HOUR_START_PARIS", "0")
    monkeypatch.setenv("ENTRY_LIQUIDITY_HOUR_END_PARIS", "23")
    monkeypatch.setenv("TP1_MIN_PTS", "10")
    monkeypatch.setenv("TP1_MAX_PTS", "20")
    from app.config import get_settings
    get_settings.cache_clear()

    from app.models import BlockedBy, DecisionPacket
    from app.engines.hard_rules import evaluate_hard_rules
    from app.state_repo import StateRow

    packet = DecisionPacket(
        session_ok=True,
        news_lock=False,
        news_next_event=None,
        news_impact_summary=[],
        news_next_event_details=None,
        news_state={"lock_active": False},
        spread=15.0,
        spread_max=25.0,
        atr=1.0,
        atr_max=50.0,
        bias_h1="UP",
        setups_detected=["PULLBACK_SR"],
        proposed_entry=4940.0,
        sl=4890.0,  # 50 pts = SL > 40
        tp1=4955.0,
        tp2=4970.0,
        rr_tp1=0.5,
        rr_tp2=0.6,
        rr_min=0.4,
        score_rules=80,
        reasons_rules=[],
        sources_used=[],
        context_summary=[],
        state={"timing_ready": True, "setup_confirm_count": 1},
        timestamps={},
        data_latency_ms=100,
    )
    state = StateRow(
        day_paris="2025-02-02",
        daily_loss_amount=0.0,
        daily_budget_amount=20.0,
        last_signal_key=None,
        last_ts=None,
        consecutive_losses=0,
        last_setup_direction="BUY",
        last_setup_entry=4940.0,
        last_setup_bar_ts=None,
        setup_confirm_count=1,
    )
    from datetime import datetime, timezone
    result = evaluate_hard_rules(packet, state, "test_key", datetime.now(timezone.utc), setup_confirm_count=1)
    assert result.blocked_by == BlockedBy.sl_too_large
    get_settings.cache_clear()


def test_rr_tp1_not_tp2(monkeypatch):
    """Score/GO dépend de RR_TP1, pas RR_TP2. TP2 énorme ne change pas NO_GO en GO."""
    monkeypatch.setenv("RR_MIN_TP1", "0.4")
    from app.config import get_settings
    get_settings.cache_clear()

    from app.engines.scorer import score_packet
    from app.models import DecisionPacket

    packet = DecisionPacket(
        session_ok=True,
        news_lock=False,
        news_next_event=None,
        news_impact_summary=[],
        news_next_event_details=None,
        news_state={"lock_active": False},
        spread=15.0,
        spread_max=25.0,
        atr=1.0,
        atr_max=50.0,
        bias_h1="UP",
        setups_detected=["PULLBACK_SR"],
        proposed_entry=4940.0,
        sl=4920.0,
        tp1=4945.0,
        tp2=5000.0,  # TP2 énorme
        rr_tp1=0.3,  # < 0.4 => pas de bonus RR
        rr_tp2=4.0,  # RR TP2 très haut
        rr_min=0.4,
        score_rules=0,
        reasons_rules=[],
        sources_used=[],
        context_summary=[],
        state={"timing_ready": True},
        timestamps={},
        data_latency_ms=100,
    )
    score, reasons = score_packet(packet)
    rr_reason = [r for r in reasons if "RR" in r]
    assert not any("TP2" in r for r in rr_reason), "Score ne doit pas mentionner RR TP2"
    get_settings.cache_clear()
