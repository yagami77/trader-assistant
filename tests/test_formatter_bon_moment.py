"""Test formatter: Bon moment detail, Explications simples removed."""
from app.infra.formatter import format_message
from app.models import DecisionResult, DecisionStatus, Quality


def test_format_no_go_with_bon_moment_detail():
    dec = DecisionResult(
        status=DecisionStatus.no_go,
        blocked_by=None,
        score_total=84,
        score_effective=84,
        confidence=84,
        quality=Quality.a,
        why=["Bon moment pas confirmé"],
    )
    msg = format_message(
        "XAUUSD",
        dec,
        4860,
        4848,
        4867,
        4870,
        "BUY",
        4863,
        "remote_mt5",
        score_reasons=[
            "Confluence H1 alignée (+10)",
            "Bon moment pas confirmé (-10)",
            "Setup clair (+25)",
        ],
        timing_step_zone_ok=True,
        timing_step_pullback_ok=False,
        timing_step_m5_ok=False,
    )
    assert "Explications simples" not in msg
    assert "Zone d'entrée" in msg
    assert "Pullback 30-50%" in msg
    assert "Rejet M5" in msg
    assert "✓" in msg
    assert "⏳" in msg


def test_format_without_timing_steps_keeps_simple_bon_moment():
    dec = DecisionResult(
        status=DecisionStatus.no_go,
        blocked_by=None,
        score_total=84,
        score_effective=84,
        confidence=84,
        quality=Quality.a,
        why=["Bon moment pas confirmé"],
    )
    msg = format_message(
        "XAUUSD",
        dec,
        4860,
        4848,
        4867,
        4870,
        "BUY",
        score_reasons=["Bon moment pas confirmé (-10)"],
    )
    assert "Bon moment pas confirmé" in msg
    assert "Explications simples" not in msg
