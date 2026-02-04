import os

from app.engines.spread_rules import evaluate_spread, is_hard_spread_block
from app.models import Bias, DecisionPacket


def _packet(spread_points: float, entry: float, sl: float) -> DecisionPacket:
    return DecisionPacket(
        session_ok=True,
        news_lock=False,
        news_next_event=None,
        news_impact_summary=[],
        news_next_event_details=None,
        news_state={},
        spread=spread_points,
        spread_max=20.0,
        spread_ratio=None,
        penalties={},
        atr=1.0,
        atr_max=2.0,
        bias_h1=Bias.up,
        direction="BUY",
        setups_detected=["A"],
        proposed_entry=entry,
        sl=sl,
        tp1=entry + 1,
        tp2=entry + 2,
        rr_tp2=2.5,
        rr_min=2.0,
        tick_size=1.0,
        score_rules=0,
        reasons_rules=[],
        sources_used=[],
        context_summary=[],
        state={},
        timestamps={"ts_utc": "2026-01-01T00:00:00+00:00", "ts_paris": "2026-01-01T01:00:00+01:00"},
        data_latency_ms=0,
    )


def test_spread_soft_penalty():
    os.environ["HARD_SPREAD_MAX_POINTS"] = "40"
    os.environ["SOFT_SPREAD_START_POINTS"] = "20"
    os.environ["SOFT_SPREAD_MAX_PENALTY"] = "30"
    os.environ["HARD_SPREAD_MAX_RATIO"] = "0.12"
    os.environ["SOFT_SPREAD_START_RATIO"] = "0.06"

    packet = _packet(spread_points=25, entry=1000, sl=700)  # sl_points=300, ratio=0.083
    eval_result = evaluate_spread(packet)
    hard, _ = is_hard_spread_block(eval_result)
    assert hard is False
    assert eval_result.penalty > 0


def test_spread_hard_block_ratio():
    os.environ["HARD_SPREAD_MAX_POINTS"] = "40"
    os.environ["SOFT_SPREAD_START_POINTS"] = "20"
    os.environ["SOFT_SPREAD_MAX_PENALTY"] = "30"
    os.environ["HARD_SPREAD_MAX_RATIO"] = "0.12"
    os.environ["SOFT_SPREAD_START_RATIO"] = "0.06"

    packet = _packet(spread_points=38, entry=1000, sl=880)  # sl_points=120, ratio=0.316
    eval_result = evaluate_spread(packet)
    hard, _ = is_hard_spread_block(eval_result)
    assert hard is True


def test_spread_hard_block_points():
    os.environ["HARD_SPREAD_MAX_POINTS"] = "40"
    os.environ["SOFT_SPREAD_START_POINTS"] = "20"
    os.environ["SOFT_SPREAD_MAX_PENALTY"] = "30"
    os.environ["HARD_SPREAD_MAX_RATIO"] = "0.12"
    os.environ["SOFT_SPREAD_START_RATIO"] = "0.06"

    packet = _packet(spread_points=41, entry=1000, sl=700)
    eval_result = evaluate_spread(packet)
    hard, _ = is_hard_spread_block(eval_result)
    assert hard is True
