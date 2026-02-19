"""
Moteur de state machine trade — mode attente intelligente.
IDLE → WATCHING → READY. GO uniquement depuis READY.
Anti-extension: bloquer si prix trop loin de la structure.
EXTENSION_MOVE adaptatif: en tendance forte + pullback confirmé, référence = last_trend_pivot.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeStateResult:
    state: str  # IDLE | WATCHING | READY
    reason: str


@dataclass(frozen=True)
class ExtensionCheckResult:
    blocked: bool
    reason: str
    distance_pts: float
    reference_level: Optional[float] = None
    impulse_dir: Optional[str] = None
    impulse_anchor_price: Optional[float] = None
    strong_trend_detected: bool = False
    pullback_confirmed: bool = False
    last_trend_pivot_price: Optional[float] = None
    final_decision: str = ""  # "allowed" | "blocked" (pour logs)


def is_pullback_confirmed(
    direction: str,
    entry: float,
    last_swing_low: Optional[float],
    last_swing_high: Optional[float],
    timing_ready: bool,
    timing_step_m5_ok: bool,
    setup_type: str,
    min_ratio: float = 0.30,
    max_ratio: float = 0.62,
    buffer_pts: float = 1.5,
) -> bool:
    """
    Pullback confirmé: retracement dans zone [min_ratio, max_ratio], rejet M5 valide,
    pas de cassure du dernier HL (BUY) ou LH (SELL).
    """
    if not timing_ready or last_swing_low is None or last_swing_high is None:
        return False
    range_pts = last_swing_high - last_swing_low
    if range_pts <= 0:
        return False
    dir_upper = direction.upper()
    if dir_upper == "BUY":
        pullback_from_high = last_swing_high - entry
        ratio = pullback_from_high / range_pts
        no_break_hl = entry >= last_swing_low - buffer_pts
        in_zone = min_ratio <= ratio <= max_ratio
        return in_zone and no_break_hl and timing_step_m5_ok
    if dir_upper == "SELL":
        pullback_from_low = entry - last_swing_low
        ratio = pullback_from_low / range_pts
        no_break_lh = entry <= last_swing_high + buffer_pts
        in_zone = min_ratio <= ratio <= max_ratio
        return in_zone and no_break_lh and timing_step_m5_ok
    return False


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
    structure_level: Optional[float],
    atr: float,
    direction: str,
    impulse_memory: Optional[dict] = None,
    setup_type: str = "ZONE_CONFIRMATION",
    timing_ready: bool = False,
    *,
    strong_trend_detected: bool = False,
    strong_trend_pivot_price: Optional[float] = None,
    pullback_confirmed: bool = False,
) -> ExtensionCheckResult:
    """
    Anti-extension: bloquer GO si prix trop loin de la structure.
    Référence dynamique: si tendance forte + pullback confirmé → reference = last_trend_pivot,
    sinon impulse_anchor ou structure_level.
    Si distance > ATR*threshold: autoriser quand même si strong_trend + pullback_confirmed.
    """
    settings = get_settings()
    threshold = getattr(settings, "impulse_extension_max_atr", None) or getattr(
        settings, "extension_atr_threshold", 0.8
    )
    retest_tol = getattr(settings, "impulse_retest_tolerance_atr", 0.35)

    reference_level = structure_level
    impulse_dir = None
    impulse_anchor = None
    if impulse_memory and structure_level is not None:
        imp_dir = impulse_memory.get("last_impulse_dir")
        imp_anchor = impulse_memory.get("impulse_anchor_price")
        if imp_dir and imp_anchor is not None:
            if (direction.upper() == "BUY" and imp_dir == "BUY") or (
                direction.upper() == "SELL" and imp_dir == "SELL"
            ):
                reference_level = imp_anchor
                impulse_dir = imp_dir
                impulse_anchor = imp_anchor

    # Référence dynamique EXTENSION_MOVE adaptatif
    if strong_trend_detected and pullback_confirmed and strong_trend_pivot_price is not None:
        reference_level = strong_trend_pivot_price

    if reference_level is None:
        return ExtensionCheckResult(
            blocked=False,
            reason="",
            distance_pts=0.0,
            strong_trend_detected=strong_trend_detected,
            pullback_confirmed=pullback_confirmed,
            last_trend_pivot_price=strong_trend_pivot_price,
            final_decision="allowed",
        )

    max_distance = atr * threshold
    distance_pts = abs(current_price - reference_level)

    # Exception retest/pullback : setup pro + timing OK + prix proche anchor (logique existante)
    if (
        setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR")
        and timing_ready
        and impulse_anchor is not None
    ):
        dist_to_anchor = abs(current_price - impulse_anchor)
        if dist_to_anchor <= atr * retest_tol:
            return ExtensionCheckResult(
                blocked=False,
                reason=f"Retest confirmé (dist_anchor={dist_to_anchor:.1f} pts <= ATR*{retest_tol})",
                distance_pts=distance_pts,
                reference_level=reference_level,
                impulse_dir=impulse_dir,
                impulse_anchor_price=impulse_anchor,
                strong_trend_detected=strong_trend_detected,
                pullback_confirmed=pullback_confirmed,
                last_trend_pivot_price=strong_trend_pivot_price,
                final_decision="allowed",
            )

    # Extension au-delà du seuil
    if distance_pts > max_distance:
        if strong_trend_detected and pullback_confirmed:
            log.info(
                "EXTENSION_MOVE adaptatif ALLOWED: current_price=%.2f reference_level=%.2f distance_pts=%.1f atr=%.1f "
                "strong_trend_detected=True pullback_confirmed=True last_trend_pivot_price=%s impulse_anchor_price=%s final_decision=allowed",
                current_price,
                reference_level,
                distance_pts,
                atr,
                strong_trend_pivot_price,
                impulse_anchor,
            )
            return ExtensionCheckResult(
                blocked=False,
                reason=f"Continuation tendance forte (ref pivot {reference_level:.2f}, dist={distance_pts:.1f} pts)",
                distance_pts=distance_pts,
                reference_level=reference_level,
                impulse_dir=impulse_dir,
                impulse_anchor_price=impulse_anchor,
                strong_trend_detected=True,
                pullback_confirmed=True,
                last_trend_pivot_price=strong_trend_pivot_price,
                final_decision="allowed",
            )
        log.info(
            "EXTENSION_MOVE BLOCKED: current_price=%.2f reference_level=%.2f distance_pts=%.1f atr=%.1f "
            "strong_trend_detected=%s pullback_confirmed=%s last_trend_pivot_price=%s impulse_anchor_price=%s final_decision=blocked",
            current_price,
            reference_level,
            distance_pts,
            atr,
            strong_trend_detected,
            pullback_confirmed,
            strong_trend_pivot_price,
            impulse_anchor,
        )
        return ExtensionCheckResult(
            blocked=True,
            reason=f"Extension ({distance_pts:.1f} pts > ATR*{threshold})",
            distance_pts=distance_pts,
            reference_level=reference_level,
            impulse_dir=impulse_dir,
            impulse_anchor_price=impulse_anchor,
            strong_trend_detected=strong_trend_detected,
            pullback_confirmed=pullback_confirmed,
            last_trend_pivot_price=strong_trend_pivot_price,
            final_decision="blocked",
        )

    return ExtensionCheckResult(
        blocked=False,
        reason="",
        distance_pts=distance_pts,
        reference_level=reference_level,
        impulse_dir=impulse_dir,
        impulse_anchor_price=impulse_anchor,
        strong_trend_detected=strong_trend_detected,
        pullback_confirmed=pullback_confirmed,
        last_trend_pivot_price=strong_trend_pivot_price,
        final_decision="allowed",
    )
