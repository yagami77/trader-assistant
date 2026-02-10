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

    if packet.setups_detected:
        pts = 25
        score += pts
        reasons.append(f"Setup clair (+{pts})")

    # 2) RR sur TP1 (uniquement bonus de score ; les hard rules gèrent les blocs)
    # Pour les NO_GO importants, on veut savoir si le RR est insuffisant.
    # On ne baisse pas le score si le RR est mauvais (les hard rules s'en chargent),
    # mais on ajoute une raison explicite le cas échéant.
    if packet.rr_tp1 >= packet.rr_min:
        pts = 20
        score += pts
        reasons.append(f"RR TP1 >= {packet.rr_min:.2f} (+{pts})")
    else:
        reasons.append(f"RR TP1 insuffisant (< {packet.rr_min:.2f})")

    # 3) Spread
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

    # 4) Volatilité (ATR)
    if packet.atr <= packet.atr_max:
        pts = 10
        score += pts
        reasons.append(f"Volatilité OK (ATR <= {packet.atr_max:.1f}) (+{pts})")

    # 5) News
    if not packet.news_lock:
        pts = 10
        score += pts
        reasons.append(f"News OK (+{pts})")

    # 6) Timing / pattern / momentum M15
    state = packet.state or {}
    timing_ready = state.get("timing_ready", False)
    setup_type = state.get("setup_type", "")
    direction = state.get("setup_direction", "BUY")
    recent_trend = state.get("recent_m15_trend", "neutral")

    if timing_ready:
        pts = 10
        score += pts
        reasons.append(f"Bon moment (zone/rejet) (+{pts})")

    if setup_type in ("BREAKOUT_RETEST", "PULLBACK_SR"):
        pts = 5
        score += pts
        reasons.append(f"Setup pro : {setup_type} (+{pts})")

    # Bon moment = aligné avec le momentum M15 (on ne bloque pas, on pousse le score)
    if recent_trend != "neutral":
        aligned = (direction == "BUY" and recent_trend == "up") or (direction == "SELL" and recent_trend == "down")
        if aligned:
            pts = 10
            score += pts
            reasons.append(f"Momentum M15 aligné (+{pts})")
        else:
            penalty = 15
            score -= penalty
            reasons.append(f"Momentum M15 contre tendance (-{penalty})")

    return max(0, score), reasons
