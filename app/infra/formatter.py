from app.models import DecisionResult, DecisionStatus, Quality


def format_go_title(symbol: str, direction: str = "BUY") -> str:
    """Titre formaté pour un signal GO (avec emoji couleur)."""
    is_buy = (direction or "BUY").upper() == "BUY"
    color_emoji = "🔵" if is_buy else "🔴"
    dir_label = "Buy" if is_buy else "Sell"
    return f"GO {dir_label} Now {color_emoji} {symbol} (M15)"


def format_message(
    symbol: str,
    decision: DecisionResult,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    direction: str = "BUY",
) -> str:
    if decision.status == DecisionStatus.no_go:
        blocked = decision.blocked_by.value if decision.blocked_by else "UNKNOWN"
        score_info = f"Score marché : {decision.score_total}/100"
        return (
            f"NO GO ❌ {symbol} (M15)\n"
            f"Bloqué par : {blocked} — {decision.why[0] if decision.why else 'Voir logs'}\n"
            f"{score_info}"
        )

    quality = "A+" if decision.quality == Quality.a_plus else "A"
    why = " + ".join(decision.why[:3]) if decision.why else "Signal validé"
    is_buy = (direction or "BUY").upper() == "BUY"
    color_emoji = "🔵" if is_buy else "🔴"
    dir_label = "Buy" if is_buy else "Sell"
    return (
        f"GO {dir_label} Now {color_emoji} {symbol} (M15)\n\n"
        f"Direction : {color_emoji} {dir_label}\n"
        f"Entrée : {entry}\n"
        f"Stop Loss : {sl}\n"
        f"TP1 : {tp1}\n"
        f"TP2 : {tp2}\n\n"
        f"Pourquoi : {why}\n"
        f"Score : {decision.score_effective}/100 — Qualité : {quality}"
    )


def format_prealert(symbol: str, news_state: dict) -> str:
    minutes = news_state.get("minutes_to_event")
    horizon = news_state.get("horizon_minutes", "")
    moment = news_state.get("moment", "")
    impact = news_state.get("next_event", {}).get("impact", "")
    title = news_state.get("next_event", {}).get("title", "")
    return (
        f"🟠 PRÉ-ALERTE {symbol} (M15)\n"
        f"📰 News: {title} ({impact})\n"
        f"⏳ Moment {moment} — dans {minutes} min — horizon {horizon} min\n"
        f"⚠️ Attention à la volatilité autour de la publication."
    )
