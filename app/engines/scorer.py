"""
Scoring en 3 blocs : Edge structurel (40), Qualité entrée (30), Risk & Execution (30).
Deux modes : Trend (H1 BULLISH/BEARISH) et Range Strategy (H1 RANGE).
Règle critique : si Edge < 28 → score_total plafonné à 85.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.config import get_settings
from app.models import DecisionPacket
from app.engines.fibo_engine import evaluate_fibo

log = logging.getLogger(__name__)


def _edge_trend(
    packet: DecisionPacket,
    state: dict,
    direction: str,
    bias: str,
    market_phase: Optional[str],
    room_to_target_ok: bool,
    settings,
) -> Tuple[int, List[str]]:
    """Mode Trend : Market Phase, Structure H1, Breakout, Room, Momentum, Fibo."""
    edge_pts = 0
    edge_reasons: List[str] = []

    if market_phase in ("IMPULSE", "PULLBACK"):
        phase_aligned = (direction == "BUY" and bias == "UP") or (direction == "SELL" and bias == "DOWN")
        if phase_aligned:
            edge_pts += 10
            edge_reasons.append("• Market Phase alignée (+10)")
        else:
            edge_reasons.append("• Market Phase non alignée (0 pt)")
    elif market_phase == "CONSOLIDATION":
        edge_reasons.append("• Market Phase CONSOLIDATION (0 pt)")
    else:
        edge_pts += 5
        edge_reasons.append("• Market Phase non évaluée (+5)")

    h1_clear = bias in ("UP", "DOWN") and (
        (direction == "BUY" and bias == "UP") or (direction == "SELL" and bias == "DOWN")
    )
    if h1_clear:
        edge_pts += 10
        edge_reasons.append("• Structure H1 claire (+10)")
    else:
        if bias == "RANGE":
            edge_reasons.append("• Structure H1 RANGE (0 pt)")
        else:
            edge_reasons.append("• Structure H1 contre tendance (0 pt)")

    setup_type = state.get("setup_type", "")
    has_breakout = setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR") and (packet.setups_detected or [])
    if has_breakout:
        edge_pts += 8
        edge_reasons.append("• Breakout validé (+8)")
    else:
        edge_reasons.append("• Breakout non validé (0 pt)")

    if room_to_target_ok:
        edge_pts += 6
        edge_reasons.append("• Room to target valide (+6)")
    else:
        edge_reasons.append("• Room to target insuffisant (0 pt)")

    recent_trend = state.get("recent_m15_trend", "neutral")
    mom_aligned = (direction == "BUY" and recent_trend == "up") or (direction == "SELL" and recent_trend == "down")
    if mom_aligned:
        edge_pts += 4
        edge_reasons.append("• Momentum M15 confirmé (+4)")
    else:
        if recent_trend == "neutral":
            edge_reasons.append("• Momentum M15 neutre (0 pt)")
        else:
            edge_reasons.append("• Momentum M15 non aligné (0 pt)")

    fibo_pts = 0
    fibo_enabled = getattr(settings, "fibo_enabled", False)
    if fibo_enabled:
        entry_price = packet.proposed_entry or 0
        swing_low = state.get("last_swing_low")
        swing_high = state.get("last_swing_high")
        fibo_signal, _ = evaluate_fibo(
            entry_price,
            direction,
            swing_low,
            swing_high,
            packet.atr or 20.0,
            zone_min=getattr(settings, "fibo_zone_min", 0.382),
            zone_max=getattr(settings, "fibo_zone_max", 0.618),
            tolerance_atr=getattr(settings, "fibo_tolerance_atr", 0.15),
        )
        if fibo_signal:
            fibo_pts = min(getattr(settings, "fibo_bonus_points", 3), 3)
            edge_pts += fibo_pts
            edge_reasons.append(f"• Fibo confluence ✓ (+{fibo_pts})")
        else:
            edge_reasons.append("• Fibo hors zone 38-62% (0 pt)")
    else:
        edge_reasons.append("• Fibo non évalué (0 pt)")

    if market_phase == "CONSOLIDATION":
        edge_pts = min(edge_pts, 25)
    edge_pts = min(edge_pts, 40)
    return edge_pts, edge_reasons


def _edge_range(
    packet: DecisionPacket,
    state: dict,
    room_to_target_ok: bool,
    settings,
) -> Tuple[int, List[str]]:
    """Mode Range Strategy (H1 == RANGE) : pas Market Phase ni Momentum obligatoires.
    Critères : Rejet borne extrême +10, Sweep high/low +8, Break structure interne +8,
    Volume spike +6, Breakout +4, Room +4. Total max 40."""
    edge_pts = 0
    edge_reasons: List[str] = []
    edge_reasons.append("• Mode RANGE (H1 range)")

    if state.get("range_rejet_borne"):
        edge_pts += 10
        edge_reasons.append("• Rejet borne extrême (+10)")
    else:
        edge_reasons.append("• Rejet borne extrême (0 pt)")

    if state.get("range_sweep"):
        edge_pts += 8
        edge_reasons.append("• Sweep high/low (+8)")
    else:
        edge_reasons.append("• Sweep high/low (0 pt)")

    if state.get("range_break_structure"):
        edge_pts += 8
        edge_reasons.append("• Break structure interne (+8)")
    else:
        edge_reasons.append("• Break structure interne (0 pt)")

    if state.get("range_volume_spike"):
        edge_pts += 6
        edge_reasons.append("• Volume spike (+6)")
    else:
        edge_reasons.append("• Volume spike (0 pt)")

    setup_type = state.get("setup_type", "")
    has_breakout = setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR") and (packet.setups_detected or [])
    if has_breakout:
        edge_pts += 4
        edge_reasons.append("• Breakout validé (+4)")
    else:
        edge_reasons.append("• Breakout non validé (0 pt)")

    if room_to_target_ok:
        edge_pts += 4
        edge_reasons.append("• Room to target valide (+4)")
    else:
        edge_reasons.append("• Room to target insuffisant (0 pt)")

    edge_pts = min(edge_pts, 40)
    return edge_pts, edge_reasons


def score_packet(
    packet: DecisionPacket,
    *,
    market_phase: Optional[str] = None,
    room_to_target_ok: bool = True,
    extension_distance_pts: Optional[float] = None,
    _debug_current_price: Optional[float] = None,
    _debug_reference_level: Optional[float] = None,
) -> Tuple[int, List[str]]:
    """
    Score 0-100 en 3 blocs. Mode Trend ou Range selon H1 (bias).
    Retourne (score_total, reasons) pour affichage Telegram.
    """
    settings = get_settings()
    state = packet.state or {}
    direction = (state.get("setup_direction") or "BUY").upper()
    bias = getattr(packet.bias_h1, "value", str(packet.bias_h1)) if packet.bias_h1 else "RANGE"
    atr = packet.atr or 20.0
    entry_reasons: List[str] = []
    risk_reasons: List[str] = []

    # --- BLOC 1 : EDGE STRUCTUREL (max 40) — Mode Trend ou Mode Range ---
    if bias == "RANGE":
        edge_pts, edge_reasons = _edge_range(packet, state, room_to_target_ok, settings)
    else:
        edge_pts, edge_reasons = _edge_trend(
            packet, state, direction, bias, market_phase, room_to_target_ok, settings
        )

    # --- BLOC 2 : QUALITÉ ENTRÉE (max 30) = Pullback ratio (+10) + Rejet M5 (+8) + timing_ready (+6) + distance extension (+6) ---
    # Extension excessive ne met plus tout le bloc à 0 : seul le critère "distance" prend 0 pt (-6).
    entry_pts = 0
    timing_ready = state.get("timing_ready", False)
    extension_threshold = atr * 1.0
    extension_excessive = (
        extension_distance_pts is not None
        and atr > 0
        and extension_distance_pts > extension_threshold
        and not timing_ready
    )
    if extension_excessive:
        log.info(
            "Extension excessive (0 pt sur distance): distance_pts=%.2f atr_pts=%.2f seuil=%.2f timing_ready=%s",
            extension_distance_pts or 0, atr, extension_threshold, timing_ready,
        )

    # +10 Pullback ratio propre (zone adaptée au mode : Trend 30-50 %, Range 20-70 %)
    entry_price = packet.proposed_entry or 0
    sl = state.get("last_swing_low")
    sh = state.get("last_swing_high")
    if sl is not None and sh is not None and sh - sl > 0:
        if direction == "BUY":
            ratio = (sh - entry_price) / (sh - sl)
        else:
            ratio = (entry_price - sl) / (sh - sl)
        # En mode RANGE (H1 RANGE) : zone large 20-70 %. En mode Trend : zone stricte 30-50 %.
        if bias == "RANGE":
            min_r, max_r = 0.20, 0.70
        else:
            min_r, max_r = 0.30, 0.50
        if min_r <= ratio <= max_r:
            entry_pts += 10
            entry_reasons.append("• Pullback ratio propre (+10)")
        else:
            entry_reasons.append(f"• Pullback hors zone {min_r:.0%}-{max_r:.0%} (0 pt)")
    else:
        entry_reasons.append("• Pullback non évalué (0 pt)")

    # +8 Rejet M5 clair
    timing_m5_ok = bool(state.get("timing_step_m5_ok")) or state.get("timing_ready", False)
    if timing_m5_ok:
        entry_pts += 8
        entry_reasons.append("• Rejet M5 clair (+8)")
    else:
        entry_reasons.append("• Rejet M5 non confirmé (0 pt)")

    # +6 timing_ready
    if state.get("timing_ready", False):
        entry_pts += 6
        entry_reasons.append("• timing_ready (+6)")
    else:
        entry_reasons.append("• timing non prêt (0 pt)")

    # +6 Pas d'extension excessive (distance < ATR * 0.8). Si extension > 1.0 ATR : 0 pt sans annuler le bloc.
    if extension_excessive:
        entry_reasons.append("• Extension excessive (0 pt)")
    elif extension_distance_pts is None or (atr > 0 and extension_distance_pts < atr * 0.8):
        entry_pts += 6
        entry_reasons.append("• Pas d'extension excessive (+6)")
    else:
        entry_reasons.append("• Extension proche seuil (0 pt)")

    entry_pts = min(entry_pts, 30)

    # --- BLOC 3 : RISK & EXECUTION (max 30) ---
    risk_pts = 0

    # +10 RR TP1 >= RR_MIN
    rr_threshold = getattr(settings, "rr_hard_min_tp1", 0.25)
    if packet.rr_tp1 >= rr_threshold:
        risk_pts += 10
        risk_reasons.append(f"• RR TP1 >= {rr_threshold:.2f} (+10)")
    else:
        risk_reasons.append("• RR TP1 insuffisant (0 pt)")

    # +6 Spread <= SPREAD_MAX
    if packet.spread <= packet.spread_max:
        risk_pts += 6
        risk_reasons.append(f"• Spread OK (<= {packet.spread_max:.0f}) (+6)")
    else:
        risk_reasons.append("• Spread trop élevé (0 pt)")

    # +6 ATR <= ATR_MAX
    if packet.atr <= packet.atr_max:
        risk_pts += 6
        risk_reasons.append(f"• ATR OK (<= {packet.atr_max:.1f}) (+6)")
    else:
        risk_reasons.append("• Volatilité trop élevée (0 pt)")

    # +8 SL cohérent (entre SL_MIN_PTS et SL_MAX_PTS) — même source que hard_rules (settings.sl_max_pts)
    risk_sl = abs((packet.proposed_entry or 0) - (packet.sl or 0))
    sl_min = getattr(settings, "sl_min_pts", 20.0)
    sl_max = getattr(settings, "sl_max_pts", 25.0)
    if risk_sl <= sl_max and risk_sl >= sl_min:
        risk_pts += 8
        risk_reasons.append("• SL cohérent (+8)")
    elif risk_sl > sl_max:
        risk_reasons.append("• SL > SL_MAX (0 pt)")
    else:
        risk_reasons.append("• SL hors fourchette (0 pt)")

    risk_pts = max(0, min(risk_pts, 30))

    # --- SCORE TOTAL ---
    score_total = edge_pts + entry_pts + risk_pts

    # Règle critique : si Edge < 28 → plafonner total à 85
    if edge_pts < 28:
        score_total = min(score_total, 85)

    score_total = max(0, min(100, score_total))

    # Emoji pour lignes : ✅ = points obtenus, 🔴 = manquant (0 pt ou négatif)
    def _bullet_icon(line: str) -> str:
        if "(+" in line or "✓" in line:
            return f"✅ {line}"
        return f"🔴 {line}"

    # Titres: emoji collé au texte (1 espace), règle remplacée par structure
    out_reasons = [
        f"🏗️ EDGE STRUCTUREL : {edge_pts}/40",
        *[_bullet_icon(r) for r in edge_reasons],
        f"🎯 QUALITÉ ENTRÉE : {entry_pts}/30",
        *[_bullet_icon(r) for r in entry_reasons],
        f"⚠️ RISK & EXECUTION : {risk_pts}/30",
        *[_bullet_icon(r) for r in risk_reasons],
        f"📊 Score total : {score_total}/100",
    ]

    return score_total, out_reasons
