from app.engines.scorer import score_packet
from app.models import DecisionPacket, Bias


def _base_packet(**overrides) -> DecisionPacket:
    data = dict(
        session_ok=True,
        news_lock=False,
        news_next_event=None,
        news_impact_summary=[],
        news_next_event_details=None,
        news_state={},
        spread=10.0,
        spread_max=25.0,
        atr=1.0,
        atr_max=50.0,
        bias_h1=Bias.up,
        setups_detected=["ZONE_CONFIRMATION"],
        proposed_entry=100.0,
        sl=99.0,
        tp1=100.5,
        tp2=101.0,
        rr_tp1=0.3,
        rr_tp2=0.6,
        rr_min=1.5,
        score_rules=0,
        reasons_rules=[],
        sources_used=[],
        context_summary=[],
        state={},
        timestamps={"ts_utc": "2026-01-01T00:00:00Z", "ts_paris": "2026-01-01T01:00:00+01:00"},
        data_latency_ms=0,
    )
    data.update(overrides)
    return DecisionPacket(**data)


def test_momentum_against_no_penalty_for_pro_setup():
    """Setup pro (BREAKOUT_RETEST/PULLBACK_SR) + momentum contre => pas de pénalité momentum."""
    packet = _base_packet(
        setups_detected=["BREAKOUT_RETEST"],
        state={
            "setup_direction": "BUY",
            "setup_type": "BREAKOUT_RETEST",
            "recent_m15_trend": "down",  # contre tendance
        },
    )
    score, reasons = score_packet(packet)
    # Aucun '-10' momentum, et la raison neutre est présente
    assert any("Momentum M15 en phase de pullback" in r for r in reasons)
    assert not any("Momentum M15 contre tendance (-" in r for r in reasons)


def test_momentum_against_penalized_for_non_pro_setup():
    """Setup non pro + momentum contre => pénalité momentum appliquée."""
    packet = _base_packet(
        setups_detected=["ZONE_CONFIRMATION"],
        state={
            "setup_direction": "BUY",
            "setup_type": "ZONE_CONFIRMATION",
            "recent_m15_trend": "down",  # contre tendance
        },
    )
    score, reasons = score_packet(packet)
    assert any("Momentum M15 contre tendance (-" in r for r in reasons)

