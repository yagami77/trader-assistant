from __future__ import annotations

from typing import Any

from app.models import Bias, DecisionResult, DecisionStatus, Quality


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


def _block_contexte(bias_h1: Bias | str | None, setups_detected: list[str] | None) -> str:
    """Contexte H1/M15 — optionnel."""
    parts: list[str] = []
    if bias_h1 is not None:
        b = getattr(bias_h1, "value", str(bias_h1))
        parts.append(f"Bias H1: {b} (direction dominante)")
    if setups_detected:
        parts.append(f"Setups M15: {', '.join(setups_detected)}")
    if not parts:
        return ""
    return "🧭 Contexte\n" + "\n".join(f"• {p}" for p in parts) + "\n\n"


def _block_news(news_state: dict[str, Any] | None) -> str:
    """News — moment, horizon, timing."""
    if not news_state:
        return ""
    minutes = news_state.get("minutes_to_event")
    horizon = news_state.get("horizon_minutes", "")
    moment = news_state.get("moment", "")
    title = news_state.get("next_event", {}).get("title", "") if isinstance(news_state.get("next_event"), dict) else ""
    impact = news_state.get("next_event", {}).get("impact", "") if isinstance(news_state.get("next_event"), dict) else ""
    if not any([minutes is not None, horizon, moment, title]):
        return ""
    lines = ["📰 News"]
    if title:
        lines.append(f"• {title}" + (f" ({impact})" if impact else ""))
    if moment:
        lines.append(f"• Moment {moment}")
    if minutes is not None and minutes != "":
        lines.append(f"• Dans {minutes} min — horizon {horizon} min" if horizon else f"• Dans {minutes} min")
    elif horizon:
        lines.append(f"• Horizon {horizon} min")
    if len(lines) <= 1:
        return ""
    return "\n".join(lines) + "\n\n"


def _block_explications(
    rr_tp1: float | None,
    rr_tp2: float | None,
    spread: float | None,
    spread_max: float | None,
    atr: float | None,
    atr_max: float | None,
    bias_h1: Bias | str | None,
) -> str:
    """Explications simples — RR, spread, volatilité, bias."""
    lines: list[str] = []
    if rr_tp1 is not None or rr_tp2 is not None:
        rr1 = _p(rr_tp1) if rr_tp1 is not None else "—"
        rr2 = _p(rr_tp2) if rr_tp2 is not None else "—"
        lines.append(f"• RR TP1: {rr1}, TP2: {rr2} (plus haut = mieux)")
    if spread is not None or spread_max is not None:
        s = _p(spread) if spread is not None else "—"
        sm = _p(spread_max) if spread_max is not None else "—"
        lines.append(f"• Spread: {s} (coût d'entrée), max {sm}")
    if atr is not None or atr_max is not None:
        a = _p(atr) if atr is not None else "—"
        am = _p(atr_max) if atr_max is not None else "—"
        lines.append(f"• Volatilité (ATR): {a}, max {am}")
    if bias_h1 is not None:
        b = getattr(bias_h1, "value", str(bias_h1))
        lines.append(f"• Bias H1: {b} (direction dominante)")
    if not lines:
        return ""
    return "🔍 Explications simples\n" + "\n".join(lines) + "\n\n"


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
    *,
    news_state: dict[str, Any] | None = None,
    spread: float | None = None,
    spread_max: float | None = None,
    atr: float | None = None,
    atr_max: float | None = None,
    rr_tp1: float | None = None,
    rr_tp2: float | None = None,
    bias_h1: Bias | str | None = None,
    setups_detected: list[str] | None = None,
    timing_step_zone_ok: bool | None = None,
    timing_step_pullback_ok: bool | None = None,
    timing_step_m5_ok: bool | None = None,
) -> str:
    dir_label = (direction or "BUY").upper()
    block_emoji = "🟦" if dir_label == "BUY" else "🟥"
    entry_f = _p(entry)
    sl_f = _p(sl)
    tp1_f = _p(tp1)
    tp2_f = _p(tp2)

    # Détails du score : on affiche la grille (exclure les erreurs de code)
    def _is_error_string(s: str) -> bool:
        lower = (s or "").lower()
        return any(x in lower for x in ("__init__", "got an unexpected", "error", "exception", "traceback", "typeerror", "attributeerror"))

    def _is_score_section_header(line: str) -> bool:
        return (
            "EDGE STRUCTUREL" in line and "/40" in line
            or "QUALITÉ ENTRÉE" in line and "/30" in line
            or "RISK & EXECUTION" in line and "/30" in line
            or "Score total" in line and "/100" in line
        )

    details_lines: list[str] = []
    if score_reasons:
        valid_reasons = [r for r in score_reasons if not _is_error_string(r)]
        if valid_reasons:
            for i, r in enumerate(valid_reasons):
                if _is_score_section_header(r):
                    if details_lines:
                        details_lines.append("")  # ligne vide avant chaque bloc
                    details_lines.append(r)
                else:
                    details_lines.append(r if r.strip().startswith("•") else f"• {r}")
        details_block = "\n".join(details_lines)
    else:
        details_block = ""

    if decision.status == DecisionStatus.no_go:
        blocked = decision.blocked_by.value if decision.blocked_by else "UNKNOWN"
        score_info = f"📊 Score global : {decision.score_total}/100"
        legend = "\n🔴 = manquant (0 pt)  |  ✅ = obtenu\n" if details_block else ""
        tail = f"{score_info}{legend}\n{details_block}" if details_block else score_info
        ctx = _block_contexte(bias_h1, setups_detected)
        news = _block_news(news_state)
        why_line = (decision.why[0] if decision.why else "Voir logs")
        if _is_error_string(why_line):
            why_line = "Données ou analyse indisponibles."
        # NO_GO : pas d'explications simples (message plus court)
        return (
            f"{block_emoji}{block_emoji}{block_emoji} {dir_label} — NO GO ❌\n\n"
            f"{symbol} (M15)\n"
            f"{ctx}{news}"
            f"Bloqué par : {blocked}\n"
            f"{why_line}\n\n"
            f"{tail}".rstrip()
        )

    quality = "A+" if decision.quality == Quality.a_plus else "A"
    quality_emoji = "⚡" if decision.quality == Quality.a_plus else "✅"
    source = _data_source_label(market_provider or "")
    prix_actuel_line = f"💰 Prix actuel {source} : {_p(current_price)}\n\n" if current_price is not None else ""
    _tp1, _tp2 = float(tp1 or 0), float(tp2 or 0)
    tp2_is_bonus = (dir_label == "BUY" and _tp2 > _tp1) or (dir_label == "SELL" and _tp2 < _tp1)
    tp2_line = f"🎯 TP2 : {tp2_f} 🎁 Bonus (optionnel)\n\n" if tp2_is_bonus else f"🎯 TP2 : {tp2_f} → Prendre le reste\n\n"

    ctx = _block_contexte(bias_h1, setups_detected)
    news = _block_news(news_state)

    return (
        f"{block_emoji}{block_emoji}{block_emoji} GO {dir_label} NOW ✅\n\n"
        f"{symbol} (M15)\n\n"
        f"{ctx}{news}"
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
        f"{details_block}".rstrip()
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
