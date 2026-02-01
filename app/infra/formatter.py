from app.models import DecisionResult, DecisionStatus, Quality


def format_message(symbol: str, decision: DecisionResult, entry: float, sl: float, tp1: float, tp2: float) -> str:
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
    return (
        f"GO ✅ {symbol} (M15)\n\n"
        f"Direction : BUY\n"
        f"Entrée : {entry}\n"
        f"Stop Loss : {sl}\n"
        f"TP1 : {tp1} → Prendre 50% + Mettre SL = Entrée\n"
        f"TP2 : {tp2} → Prendre le reste\n\n"
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
