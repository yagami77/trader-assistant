"""
Moteur de state machine trade — mode attente intelligente.
IDLE → WATCHING → READY. GO uniquement depuis READY.
Anti-extension: bloquer si prix trop loin de la structure.
Renforce sans modifier les règles existantes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import get_settings


@dataclass(frozen=True)
class TradeStateResult:
    state: str  # IDLE | WATCHING | READY
    reason: str


@dataclass(frozen=True)
class ExtensionCheckResult:
    blocked: bool
    reason: str
    distance_pts: float


def evaluate_trade_state(
    setups_detected: list,
    timing_ready: bool,
    structure_h1: str,
    setup_type: str,
    direction: str,
) -> TradeStateResult:
    """
    Évalue l'état de la state machine.
    IDLE: aucun setup structuré
    WATCHING: structure intéressante, timing pas confirmé
    READY: confluence validée, déclencheur prêt
    """
    if not setups_detected:
        return TradeStateResult("IDLE", "Aucun setup détecté")

    if not timing_ready:
        return TradeStateResult(
            "WATCHING",
            f"Setup détecté ({setup_type}) — timing non confirmé",
        )

    # Confluence: H1 aligné ou neutre (RANGE accepté)
    h1_ok = structure_h1 in ("BULLISH", "BEARISH", "RANGE")
    if not h1_ok:
        return TradeStateResult("WATCHING", "Structure H1 non validée")

    return TradeStateResult(
        "READY",
        f"Confluence validée — {setup_type} {direction}",
    )


def check_extension_blocked(
    current_price: float,
    structure_level: float,
    atr: float,
    direction: str,
) -> ExtensionCheckResult:
    """
    Anti-extension: bloquer GO si prix trop loin de la structure (entrée en fin de mouvement).
    structure_level = swing_low (BUY) ou swing_high (SELL).
    """
    settings = get_settings()
    threshold = getattr(settings, "extension_atr_threshold", 0.8)
    max_distance = atr * threshold
    distance = abs(current_price - structure_level)

    if distance > max_distance:
        return ExtensionCheckResult(
            blocked=True,
            reason=f"Extension ({distance:.1f} pts > ATR*{threshold})",
            distance_pts=distance,
        )
    return ExtensionCheckResult(blocked=False, reason="", distance_pts=distance)
