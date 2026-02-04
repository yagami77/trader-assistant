from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from datetime import datetime

from app.models import Bias, BlockedBy, DecisionPacket
from app.engines.spread_rules import evaluate_spread, is_hard_spread_block
from app.state_repo import StateRow, is_budget_reached, is_cooldown_ok


@dataclass(frozen=True)
class HardRuleResult:
    blocked_by: Optional[BlockedBy]
    reason: Optional[str]


def _is_h1_m15_aligned(packet: DecisionPacket) -> bool:
    """Vérifie que le bias H1 confirme la direction M15 (confluence HTF+LTF)."""
    direction = (packet.direction or "BUY").upper()
    bias_h1 = packet.bias_h1
    if bias_h1 == Bias.range:
        return True
    if direction == "BUY" and bias_h1 == Bias.down:
        return False
    if direction == "SELL" and bias_h1 == Bias.up:
        return False
    return True


def evaluate_hard_rules(
    packet: DecisionPacket, state: StateRow, signal_key: str, now_utc: datetime
) -> HardRuleResult:
    if not packet.session_ok:
        return HardRuleResult(BlockedBy.out_of_session, "Hors fenêtre de trading")
    if not _is_h1_m15_aligned(packet):
        return HardRuleResult(
            BlockedBy.bias_h1_mismatch,
            f"H1 {packet.bias_h1.value} ne confirme pas {packet.direction} M15",
        )
    if packet.news_state.get("lock_active"):
        return HardRuleResult(BlockedBy.news_lock, "News high impact")
    spread_eval = evaluate_spread(packet)
    hard_block, reason = is_hard_spread_block(spread_eval)
    if hard_block:
        ratio_txt = (
            f", ratio {spread_eval.spread_ratio:.2%}" if spread_eval.spread_ratio is not None else ""
        )
        return HardRuleResult(
            BlockedBy.spread_too_high,
            f"{reason}: {spread_eval.spread_points:.1f} pts{ratio_txt}",
        )
    if packet.atr > packet.atr_max:
        return HardRuleResult(BlockedBy.volatility_too_high, "Volatilité trop élevée")
    if packet.rr_tp2 < packet.rr_min:
        return HardRuleResult(BlockedBy.rr_too_low, "RR TP2 insuffisant")
    if is_budget_reached(state):
        return HardRuleResult(BlockedBy.daily_budget_reached, "Budget journalier atteint")
    if not is_cooldown_ok(state, now_utc):
        return HardRuleResult(BlockedBy.duplicate_signal, "Cooldown actif")
    if state.last_signal_key == signal_key:
        return HardRuleResult(BlockedBy.duplicate_signal, "Signal dupliqué")
    return HardRuleResult(None, None)
