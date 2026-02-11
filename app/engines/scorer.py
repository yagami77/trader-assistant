from typing import List, Tuple

from app.config import get_settings
from app.models import DecisionPacket


def score_packet(packet: DecisionPacket) -> Tuple[int, List[str]]:
    """
    Calcule un score 0-100 et une liste de raisons textuelles avec le détail des points.
    On garde la même grille qu'avant, mais on explicite les points dans les libellés
    pour pouvoir les afficher clairement dans Telegram.
    """
    score = 0
    reasons: List[str] = []

    # 1) Contexte H1 (confluence, pas blocage) : +10 si aligné, 0 si contre (pas de pénalité)
    state = packet.state or {}
    direction = state.get("setup_direction", "BUY")
    bias = getattr(packet.bias_h1, "value", str(packet.bias_h1)) if packet.bias_h1 is not None else "RANGE"
    h1_aligned = (direction == "BUY" and bias == "UP") or (direction == "SELL" and bias == "DOWN")
    h1_against = (direction == "BUY" and bias == "DOWN") or (direction == "SELL" and bias == "UP")
    if h1_aligned:
        pts = 10
        score += pts
        reasons.append(f"Confluence H1 alignée (+{pts})")
    elif h1_against:
        reasons.append("H1 contre tendance (0 pt)")
    else:
        reasons.append("H1 neutre (0 pt)")

    if packet.setups_detected:
        pts = 25
        score += pts
        reasons.append(f"Setup clair (+{pts})")
    else:
        reasons.append("Aucun setup (0 pt)")

    # 2) RR sur TP1 : bonus uniquement, jamais blocage (scalp = TP courts OK).
    # En mode scalp on utilise un seuil bas (rr_hard_min_tp1) pour attribuer le bonus.
    settings = get_settings()
    is_scalp = (getattr(settings, "mode_trading", "") or "").lower() == "scalp"
    rr_threshold = getattr(settings, "rr_hard_min_tp1", 0.15) if is_scalp else packet.rr_min
    if packet.rr_tp1 >= rr_threshold:
        pts = 20
        score += pts
        reasons.append(f"RR TP1 >= {rr_threshold:.2f} (+{pts})")
    else:
        # Formulation neutre : pas de "insuffisant", juste pas de bonus
        reasons.append(f"RR TP1 court (0 pt)")

    # 3) Spread — toujours une ligne
    if packet.spread <= packet.spread_max:
        base_pts = 10
        score += base_pts
        reasons.append(f"Spread OK (<= {packet.spread_max:.0f}) (+{base_pts})")
        settings = get_settings()
        if packet.spread > settings.soft_spread_start_pts:
            penalty = min(5, int((packet.spread - settings.soft_spread_start_pts) / 2))
            score -= penalty
            if penalty > 0:
                reasons.append(f"Pénalité spread soft (-{penalty})")
    else:
        reasons.append("Spread trop élevé (0 pt)")

    # 4) Volatilité (ATR) — toujours une ligne
    if packet.atr <= packet.atr_max:
        pts = 10
        score += pts
        reasons.append(f"Volatilité OK (ATR <= {packet.atr_max:.1f}) (+{pts})")
    else:
        reasons.append("Volatilité trop élevée (0 pt)")

    # 5) News — +5 uniquement si API TradingEconomics branchée (guest:guest), pas mock
    if packet.news_lock:
        reasons.append("News lock (0 pt)")
    elif settings.news_provider.lower() == "tradingeconomics" and packet.news_state.get("provider_ok"):
        pts = 5
        score += pts
        reasons.append(f"News OK — API TE (+{pts})")
    else:
        reasons.append("News OK (mock ou API down, 0 pt)")

    # 6) Timing / pattern / momentum M15
    state = packet.state or {}
    timing_ready = state.get("timing_ready", False)
    setup_type = state.get("setup_type", "")
    direction = state.get("setup_direction", "BUY")
    recent_trend = state.get("recent_m15_trend", "neutral")

    # Bon moment — toujours une ligne
    if timing_ready:
        pts = 10
        score += pts
        reasons.append(f"Bon moment (zone/rejet) (+{pts})")
    else:
        pts = 10
        score -= pts
        reasons.append(f"Bon moment pas confirmé (-{pts})")

    # Setup pro — toujours une ligne
    if setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR"):
        pts = 5
        score += pts
        reasons.append(f"Setup pro : {setup_type} (+{pts})")
    else:
        reasons.append("Setup non pro (0 pt)")

    # Momentum M15 — toujours une ligne, mais pénalité conditionnelle au type de setup
    if recent_trend != "neutral":
        aligned = (direction == "BUY" and recent_trend == "up") or (direction == "SELL" and recent_trend == "down")
        if aligned:
            pts = 10
            score += pts
            reasons.append(f"Momentum M15 aligné (+{pts})")
        else:
            # Setup principal « pro » (retest / pullback) => momentum contre = phase de pullback, neutre
            setups = packet.setups_detected or []
            has_pro_setup = setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR") or any(
                s in ("BREAKOUT_RETEST", "PULLBACK_SR") for s in setups
            )
            if has_pro_setup:
                reasons.append("Momentum M15 en phase de pullback (neutre, 0 pt)")
            else:
                penalty = getattr(get_settings(), "momentum_against_penalty", 10)
                score -= penalty
                reasons.append(f"Momentum M15 contre tendance (-{penalty})")
    else:
        reasons.append("Momentum M15 neutre (0 pt)")

    # 7) M5 — aligné +10, contre -10, neutre 0
    m5_trend = state.get("m5_trend", "neutral")
    if m5_trend == "aligned":
        pts = 10
        score += pts
        reasons.append(f"M5 aligné (+{pts})")
    elif m5_trend == "against":
        pts = 10
        score -= pts
        reasons.append(f"M5 contre (-{pts})")
    else:
        reasons.append("M5 neutre (0 pt)")

    return max(0, score), reasons
