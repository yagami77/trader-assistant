from app.models import DecisionResult, DecisionStatus, Quality


def _data_source_label(market_provider: str) -> str:
    """Indique si les prix viennent du MT5 en direct ou du mock (pour éviter les confusions)."""
    if (market_provider or "").lower() == "remote_mt5":
        return "MT5 (live)"
    return "MOCK" if (market_provider or "").lower() == "mock" else (market_provider or "?")


def _p(v: float | None) -> str:
    """Prix formaté à 2 décimales."""
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def format_message(
    symbol: str,
    decision: DecisionResult,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    direction: str = "BUY",
    current_price: float | None = None,
    market_provider: str | None = None,
    score_reasons: list[str] | None = None,
) -> str:
    dir_label = (direction or "BUY").upper()
    block_emoji = "🟦" if dir_label == "BUY" else "🟥"
    entry_f = _p(entry)
    sl_f = _p(sl)
    tp1_f = _p(tp1)
    tp2_f = _p(tp2)

    # Détails du score : on affiche la grille complète (avec les points) si disponible
    details_lines: list[str] = []
    if score_reasons:
        details_lines.append("Détails du score :")
        for r in score_reasons:
            details_lines.append(f"• {r}")
        details_block = "\n".join(details_lines)
    else:
        details_block = ""

    if decision.status == DecisionStatus.no_go:
        blocked = decision.blocked_by.value if decision.blocked_by else "UNKNOWN"
        score_info = f"Score global : {decision.score_total}/100"
        tail = f"{score_info}\n\n{details_block}" if details_block else score_info
        return (
            f"{block_emoji}{block_emoji}{block_emoji} {dir_label} — NO GO ❌\n\n"
            f"{symbol} (M15)\n"
            f"Bloqué par : {blocked}\n"
            f"{decision.why[0] if decision.why else 'Voir logs'}\n\n"
            f"{tail}"
        )

    quality = "A+" if decision.quality == Quality.a_plus else "A"
    quality_emoji = "⚡" if decision.quality == Quality.a_plus else "✅"
    source = _data_source_label(market_provider or "")
    prix_actuel_line = f"💰 Prix actuel {source} : {_p(current_price)}\n\n" if current_price is not None else ""
    _tp1, _tp2 = float(tp1 or 0), float(tp2 or 0)
    tp2_is_bonus = (dir_label == "BUY" and _tp2 > _tp1) or (dir_label == "SELL" and _tp2 < _tp1)
    tp2_line = f"🎯 TP2 : {tp2_f} 🎁 Bonus (optionnel)\n\n" if tp2_is_bonus else f"🎯 TP2 : {tp2_f} → Prendre le reste\n\n"

    return (
        f"{block_emoji}{block_emoji}{block_emoji} GO {dir_label} NOW ✅\n\n"
        f"{symbol} (M15)\n\n"
        f"{prix_actuel_line}"
        f"➡️ Entrée : {entry_f}\n"
        f"⛔ SL : {sl_f}\n"
        f"🎯 TP1 : {tp1_f} → Objectif principal (BE/fermé)\n"
        f"{tp2_line}"
        f"📋 SUIVI\n"
        f"• TP1 atteint → réduire 50%, SL à l'entrée (BE)\n"
        f"• TP2 atteint → fermer le reste\n"
        f"• SL touché → sortie complète\n\n"
        f"💎 Setup de qualité {quality} {quality_emoji}\n"
        f"Score global : {decision.score_effective}/100\n\n"
        f"{details_block}"
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
