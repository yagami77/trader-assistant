from typing import List, Tuple

from app.models import DecisionPacket


def score_packet(packet: DecisionPacket) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    if packet.bias_h1:
        score += 25
        reasons.append("Bias H1 aligné")

    if packet.setups_detected:
        score += 25
        reasons.append("Setup clair")

    if packet.rr_tp2 >= packet.rr_min:
        score += 20
        reasons.append(f"RR TP2 >= {packet.rr_min}")

    if packet.spread <= packet.spread_max:
        score += 10
        reasons.append("Spread OK")

    if packet.atr <= packet.atr_max:
        score += 10
        reasons.append("Volatilité OK")

    if not packet.news_lock:
        score += 10
        reasons.append("News OK")

    return score, reasons
