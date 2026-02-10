from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from datetime import datetime

from app.config import get_settings
from app.models import BlockedBy, DecisionPacket
from app.state_repo import StateRow, is_budget_reached, is_cooldown_ok


@dataclass(frozen=True)
class HardRuleResult:
    blocked_by: Optional[BlockedBy]
    reason: Optional[str]


def evaluate_hard_rules(
    packet: DecisionPacket, state: StateRow, signal_key: str, now_utc: datetime,
    setup_confirm_count: int = 1,
) -> HardRuleResult:
    settings = get_settings()
    if not packet.session_ok:
        return HardRuleResult(BlockedBy.out_of_session, "Hors fenêtre de trading")
    if packet.news_state.get("lock_active"):
        return HardRuleResult(BlockedBy.news_lock, "News high impact")
    if packet.spread >= settings.hard_spread_max_pts:
        return HardRuleResult(
            BlockedBy.spread_too_high,
            f"Spread trop élevé (hard block: {packet.spread:.0f} >= {settings.hard_spread_max_pts})",
        )
    # Ratio spread/risque : ignoré si spread <= SPREAD_MAX (XAUUSD Vantage 20-21 pts OK)
    risk = abs((packet.proposed_entry or 0) - (packet.sl or 0))
    if risk > settings.sl_max_pts:
        return HardRuleResult(
            BlockedBy.sl_too_large,
            f"SL trop large (risque {risk:.0f} > {settings.sl_max_pts} pts)",
        )
    if (
        packet.spread > packet.spread_max
        and risk > 0.01
        and packet.spread > risk * settings.hard_spread_max_ratio
    ):
        return HardRuleResult(
            BlockedBy.spread_too_high,
            f"Spread/risque trop élevé (ratio {packet.spread/risk:.2f} > {settings.hard_spread_max_ratio})",
        )
    if packet.spread > packet.spread_max:
        return HardRuleResult(BlockedBy.spread_too_high, "Spread trop élevé")
    if packet.atr > packet.atr_max:
        return HardRuleResult(BlockedBy.volatility_too_high, "Volatilité trop élevée")
    rr_min = getattr(settings, "rr_min_tp1", settings.rr_min)
    rr_hard = getattr(settings, "rr_hard_min_tp1", 0.2)
    if packet.rr_tp1 < rr_hard:
        return HardRuleResult(
            BlockedBy.rr_too_low,
            f"RR TP1 extrêmement faible ({packet.rr_tp1:.2f} < {rr_hard:.2f})",
        )
    if packet.rr_tp1 < rr_min:
        return HardRuleResult(
            BlockedBy.rr_too_low,
            f"RR TP1 insuffisant ({packet.rr_tp1:.2f} < {rr_min:.2f})",
        )
    if is_budget_reached(state):
        return HardRuleResult(BlockedBy.daily_budget_reached, "Budget journalier atteint")
    if not is_cooldown_ok(state, now_utc):
        return HardRuleResult(BlockedBy.duplicate_signal, "Cooldown actif")
    # Après cooldown, autoriser même setup (rappel). Même signal_key seul ne bloque plus.
    if setup_confirm_count < settings.setup_confirm_min_bars:
        return HardRuleResult(
            BlockedBy.setup_not_confirmed,
            f"Setup non confirmé ({setup_confirm_count}/{settings.setup_confirm_min_bars} barres)",
        )
    return HardRuleResult(None, None)
