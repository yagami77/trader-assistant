from typing import List, Tuple

from app.models import Bias, DecisionPacket
from app.engines.spread_rules import evaluate_spread


def score_packet(packet: DecisionPacket) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    spread_eval = evaluate_spread(packet)
    packet.spread_ratio = spread_eval.spread_ratio
    packet.penalties = {
        "spread_penalty": spread_eval.penalty,
        "spread_points": spread_eval.spread_points,
        "spread_ratio": spread_eval.spread_ratio,
    }

    if packet.bias_h1 and packet.bias_h1 != Bias.range:
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
    if spread_eval.penalty > 0:
        score -= spread_eval.penalty
        ratio_txt = (
            f" (~{spread_eval.spread_ratio:.2%} du SL)" if spread_eval.spread_ratio is not None else ""
        )
        reasons.append(
            f"Spread élevé: {spread_eval.spread_points:.1f} pts{ratio_txt} (-{spread_eval.penalty})"
        )

    if packet.atr <= packet.atr_max:
        score += 10
        reasons.append("Volatilité OK")

    if not packet.news_lock:
        score += 10
        reasons.append("News OK")

    return score, reasons
