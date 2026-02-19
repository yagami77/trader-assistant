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
    # Heures liquides : éviter GO 0h-8h Paris (faible liquidité XAU)
    h_start = getattr(settings, "entry_liquidity_hour_start_paris", 8)
    h_end = getattr(settings, "entry_liquidity_hour_end_paris", 23)
    # now_utc en heure Paris (approximation via session)
    from zoneinfo import ZoneInfo
    now_paris = now_utc.astimezone(ZoneInfo("Europe/Paris"))
    h = now_paris.hour
    if h_start <= h_end:  # ex: 8-23
        if h < h_start or h > h_end:
            return HardRuleResult(
                BlockedBy.low_liquidity,
                f"Hors heures liquides ({h}h Paris, fenêtre {h_start}h-{h_end}h)",
            )
    else:  # ex: 22-6 (nuit)
        if h > h_end and h < h_start:
            return HardRuleResult(
                BlockedBy.low_liquidity,
                f"Hors heures liquides ({h}h Paris)",
            )
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
    # RR scalp : SEUL RR_HARD_MIN_TP1 peut bloquer (ex: 0.25). RR_MIN (1.5) et RR_MIN_TP1 (0.3) ne bloquent pas.
    rr_hard = getattr(settings, "rr_hard_min_tp1", 0.25)
    if packet.rr_tp1 < rr_hard:
        return HardRuleResult(
            BlockedBy.rr_too_low,
            f"RR TP1 extrêmement faible ({packet.rr_tp1:.2f} < {rr_hard:.2f})",
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
