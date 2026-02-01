from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from datetime import datetime

from app.models import BlockedBy, DecisionPacket
from app.state_repo import StateRow, is_budget_reached, is_cooldown_ok


@dataclass(frozen=True)
class HardRuleResult:
    blocked_by: Optional[BlockedBy]
    reason: Optional[str]


def evaluate_hard_rules(
    packet: DecisionPacket, state: StateRow, signal_key: str, now_utc: datetime
) -> HardRuleResult:
    if not packet.session_ok:
        return HardRuleResult(BlockedBy.out_of_session, "Hors fenêtre de trading")
    if packet.news_state.get("lock_active"):
        return HardRuleResult(BlockedBy.news_lock, "News high impact")
    if packet.spread > packet.spread_max:
        return HardRuleResult(BlockedBy.spread_too_high, "Spread trop élevé")
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
