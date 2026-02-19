"""
Moteur SUIVI — après un GO, suit le trade jusqu'à TP ou SL.
MAINTIEN / ALERTE (retournement, résistance, patterns contre) / SORTIE (TP ou SL atteint).
Logique qualitative marché : structure M15, S/R, pin bar/engulfing contre, news HIGH imminente.
Ordre obligatoire : TP1 d'abord, puis TP2 (TP2 déclaré uniquement si be_applied = TP1 déjà passé).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.engines.entry_timing_engine import (
    _is_rejection_candle_bearish,
    _is_rejection_candle_bullish,
)
from app.engines.structure_engine import analyze_structure


@dataclass(frozen=True)
class SuiviResult:
    status: str  # "MAINTIEN" | "ALERTE" | "SORTIE"
    message: str
    closed: bool  # True = trade terminé, revenir à la normale
    outcome_pips: Optional[float] = None  # Résultat en pips (positif = profit, négatif = perte) pour le résumé du jour


def _p(v: float) -> str:
    return f"{v:.2f}"


def _msg_sl(entry: float, sl: float, price_touched: float, direction: str) -> str:
    """Message SORTIE SL."""
    if direction.upper() == "BUY":
        pts = round(entry - sl, 2)
    else:
        pts = round(sl - entry, 2)
    return (
        f"😔 SL touché — trade raté\n\n"
        f"📊 Résultat du trade: PERTE — {pts:.1f} point\n\n"
        f"Prix: {_p(price_touched)} | SL: {_p(sl)}\n"
        f"On va récupérer dans la journée, on va faire mieux !\n"
        f"Trade clôturé. Prochaine opportunité."
    )


def _msg_tp1(entry: float, tp1: float, price_touched: float, direction: str) -> str:
    """Message SORTIE TP1 (via bougies)."""
    if direction.upper() == "BUY":
        pts = round(tp1 - entry, 2)
    else:
        pts = round(entry - tp1, 2)
    return (
        f"🎉 Bravo ! TP1 atteint\n\n"
        f"📊 Résultat du trade: PROFIT +{pts:.1f} point\n\n"
        f"Prix: {_p(price_touched)} | TP1: {_p(tp1)}\n"
        f"Objectif principal atteint. À la prochaine !"
    )


def _msg_tp1_be(
    entry: float, sl_be: float, tp2: float, direction: str, pts_tp1: float,
    tp1_close_percent: float = 0.0,
) -> str:
    """Message TP1 atteint + SL passé à BE (= entrée, jamais TP1). tp1_close_percent > 0 = clôture partielle."""
    dir_emoji = "🟦" if direction.upper() == "BUY" else "🟥"
    if tp1_close_percent > 0:
        pts_realises = round(pts_tp1 * tp1_close_percent / 100.0, 1)
        pts_line = f"💰 +{pts_realises:.1f} pts réalisés ({tp1_close_percent:.0f}% clôturé au TP1)\n\n"
    else:
        pts_line = f"💰 +{pts_tp1:.1f} pts réalisés (TP1)\n\n"
    return (
        f"🎉 Bravo ! TP1 atteint\n\n"
        f"✅ SL passé à Break-even (= entrée)\n\n"
        f"{dir_emoji} {direction.upper()} XAUUSD\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"➡️ Entrée : {entry:.2f}\n"
        f"⛔ SL (BE) : {sl_be:.2f} (= prix d'entrée)\n"
        f"🎯 TP2 : {tp2:.2f}\n\n"
        f"{pts_line}"
        f"📈 On laisse courir vers TP2 !\n"
        f"⚠️ Déplace le SL sur MT5 à ce niveau si ce n'est pas fait automatiquement."
    )


def _msg_tp2(entry: float, tp2: float, price_touched: float, direction: str) -> str:
    """Message SORTIE TP2."""
    if direction.upper() == "BUY":
        pts = round(tp2 - entry, 2)
    else:
        pts = round(entry - tp2, 2)
    return (
        f"🎉 Bravo ! TP2 atteint\n\n"
        f"📊 Résultat du trade: PROFIT +{pts:.1f} point\n\n"
        f"Prix: {_p(price_touched)} | TP2: {_p(tp2)}\n"
        f"Trade réussi, objectif bonus. À la prochaine !"
    )


def _is_engulfing_bearish(prev: dict, curr: dict) -> bool:
    """Engulfing baissier : prev haussier, curr baissier englobe prev."""
    po, pc = float(prev.get("open", 0)), float(prev.get("close", 0))
    co, cc = float(curr.get("open", 0)), float(curr.get("close", 0))
    if po <= pc and co >= cc:  # prev bullish, curr bearish
        return co >= pc and cc <= po  # curr engulfs prev
    return False


def _is_engulfing_bullish(prev: dict, curr: dict) -> bool:
    """Engulfing haussier : prev bearish, curr bullish engulfs prev."""
    po, pc = float(prev.get("open", 0)), float(prev.get("close", 0))
    co, cc = float(curr.get("open", 0)), float(curr.get("close", 0))
    if po >= pc and co <= cc:  # prev bearish, curr bullish
        return co <= pc and cc >= po  # curr engulfs prev
    return False


def _is_news_high_imminent(news_state: Dict[str, Any]) -> bool:
    """News HIGH imminente (fenêtre pré-event)."""
    if not news_state:
        return False
    next_ev = news_state.get("next_event") or {}
    impact = str(next_ev.get("impact", "")).upper()
    if impact != "HIGH":
        return False
    minutes = news_state.get("minutes_to_event")
    if minutes is None:
        return bool(news_state.get("lock_active"))
    return minutes <= 30 and minutes > 0


def _check_structure_m15_broken(
    direction: str,
    current_price: float,
    last_swing_low: Optional[float],
    last_swing_high: Optional[float],
) -> bool:
    """
    BUY : cassure si prix < dernier HL (swing low).
    SELL : cassure si prix > dernier LH (swing high).
    """
    if direction.upper() == "BUY":
        if last_swing_low is None:
            return False
        return current_price < last_swing_low
    else:
        if last_swing_high is None:
            return False
        return current_price > last_swing_high


def _check_sr_too_close(
    direction: str,
    current_price: float,
    entry: float,
    tp1: float,
    sr_levels: List[float],
    sr_buffer_pts: float,
) -> bool:
    """
    BUY : résistance (niveau au-dessus du prix) à moins de sr_buffer_pts.
    SELL : support (niveau en-dessous du prix) à moins de sr_buffer_pts.
    """
    for level in sr_levels:
        dist = abs(level - current_price)
        if dist < sr_buffer_pts:
            if direction.upper() == "BUY" and level > current_price:
                return True
            if direction.upper() == "SELL" and level < current_price:
                return True
    return False


def _check_pin_bar_against(candles: List[dict], direction: str) -> bool:
    """Pin bar contre le sens du trade sur les 3 dernières bougies."""
    if not candles or len(candles) < 1:
        return False
    last_3 = candles[-3:] if len(candles) >= 3 else candles
    for c in last_3:
        if direction.upper() == "BUY" and _is_rejection_candle_bearish(c):
            return True
        if direction.upper() == "SELL" and _is_rejection_candle_bullish(c):
            return True
    return False


def _check_engulfing_against(candles: List[dict], direction: str) -> bool:
    """Engulfing contre le sens du trade sur les 2 dernières bougies."""
    if not candles or len(candles) < 2:
        return False
    prev, curr = candles[-2], candles[-1]
    if direction.upper() == "BUY" and _is_engulfing_bearish(prev, curr):
        return True
    if direction.upper() == "SELL" and _is_engulfing_bullish(prev, curr):
        return True
    return False


def _check_stagnation_near_key_zone(
    candles: List[dict],
    current_price: float,
    sr_levels: List[float],
    sr_buffer_pts: float,
) -> bool:
    """Stagnation près d'une zone clé (prix oscille autour d'un S/R)."""
    if not candles or len(candles) < 3 or not sr_levels:
        return False
    for level in sr_levels:
        if abs(level - current_price) <= sr_buffer_pts:
            return True
    return False


def evaluate_suivi(
    current_price: float,
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    structure_h1: str,
    candles_m15: List[dict],
    news_state: Optional[Dict[str, Any]] = None,
    sr_buffer_points: float = 25.0,
    active_started_ts: Optional[str] = None,
    be_enabled: bool = False,
    be_applied: bool = False,
    be_offset_pts: float = 0.0,
    tp1_close_percent: float = 0.0,
) -> SuiviResult:
    """
    Évalue le suivi du trade actif (logique qualitative marché).
    - SORTIE: TP1 (si BE désactivé), TP2 ou SL atteint
    - TP1_BE: TP1 atteint + BE activé → SL passé à entrée, continuer vers TP2 (closed=False)
    - ALERTE: au moins un signal (S/R proche, cassure structure, pin bar/engulfing contre, stagnation)
    - MAINTIEN: uniquement si TOUS les critères OK (structure M15 valide, pas S/R proche,
      pas de pattern contre, pas de news HIGH imminente)
    """
    news_state = news_state or {}
    struct_m15 = analyze_structure(candles_m15) if candles_m15 else None
    last_hl = struct_m15.last_swing_low if struct_m15 else None
    last_lh = struct_m15.last_swing_high if struct_m15 else None
    sr_levels = struct_m15.sr_levels if struct_m15 else []

    # --- SORTIE : SL, puis TP1, puis TP2 (TP2 uniquement si be_applied = TP1 déjà passé) ---
    if direction.upper() == "BUY":
        if current_price <= sl:
            pts = round(entry - sl, 2)
            return SuiviResult(
                status="SORTIE",
                message=_msg_sl(entry, sl, current_price, direction),
                closed=True,
                outcome_pips=-pts,
            )
        # TP2 : seulement si TP1 déjà passé (be_applied) — évite "TP2 d'un coup" sans TP1
        if be_applied and current_price >= tp2:
            pts = round(tp2 - entry, 2)
            return SuiviResult(
                status="SORTIE",
                message=_msg_tp2(entry, tp2, current_price, direction),
                closed=True,
                outcome_pips=pts,
            )
        if current_price >= tp1:
            pts = round(tp1 - entry, 2)
            if be_enabled and not be_applied:
                sl_be = entry + be_offset_pts  # BE = entrée, jamais TP1
                return SuiviResult(
                    status="TP1_BE",
                    message=_msg_tp1_be(entry, sl_be, tp2, direction, pts, tp1_close_percent),
                    closed=False,
                )
            # BE déjà appliqué : on est entre TP1 et TP2, on laisse courir (pas de 2e message TP1)
            if be_enabled and be_applied:
                pass  # fallthrough → MAINTIEN / ALERTE
            else:
                return SuiviResult(
                    status="SORTIE",
                    message=_msg_tp1(entry, tp1, current_price, direction),
                    closed=True,
                    outcome_pips=pts,
                )
    else:
        if current_price >= sl:
            pts = round(sl - entry, 2)
            return SuiviResult(
                status="SORTIE",
                message=_msg_sl(entry, sl, current_price, direction),
                closed=True,
                outcome_pips=-pts,
            )
        if be_applied and current_price <= tp2:
            pts = round(entry - tp2, 2)
            return SuiviResult(
                status="SORTIE",
                message=_msg_tp2(entry, tp2, current_price, direction),
                closed=True,
                outcome_pips=pts,
            )
        if current_price <= tp1:
            pts = round(entry - tp1, 2)
            if be_enabled and not be_applied:
                sl_be = entry - be_offset_pts  # BE = entrée, jamais TP1
                return SuiviResult(
                    status="TP1_BE",
                    message=_msg_tp1_be(entry, sl_be, tp2, direction, pts, tp1_close_percent),
                    closed=False,
                )
            # BE déjà appliqué : on est entre TP1 et TP2, on laisse courir (pas de 2e message TP1)
            if be_enabled and be_applied:
                pass  # fallthrough → MAINTIEN / ALERTE
            else:
                return SuiviResult(
                    status="SORTIE",
                    message=_msg_tp1(entry, tp1, current_price, direction),
                    closed=True,
                    outcome_pips=pts,
                )

    # --- ALERTE : au moins un signal ---
    sr_too_close = _check_sr_too_close(
        direction, current_price, entry, tp1, sr_levels, sr_buffer_points
    )
    structure_broken = _check_structure_m15_broken(direction, current_price, last_hl, last_lh)
    pin_bar_against = _check_pin_bar_against(candles_m15, direction)
    engulfing_against = _check_engulfing_against(candles_m15, direction)
    stagnation = _check_stagnation_near_key_zone(
        candles_m15, current_price, sr_levels, sr_buffer_points
    )
    structure_h1_against = (
        (direction == "BUY" and structure_h1 == "BEARISH")
        or (direction == "SELL" and structure_h1 == "BULLISH")
    )

    if sr_too_close or structure_broken or pin_bar_against or engulfing_against or stagnation or structure_h1_against:
        # Gain actuel en points (positif si le trade est en gain)
        if direction.upper() == "BUY":
            gain_pts = current_price - entry
        else:
            gain_pts = entry - current_price
        gain_pts = float(gain_pts)

        # Seuil minimum pour parler de BE / partiel
        min_gain_for_be = 5.0

        # Infos utiles : distance au TP1, distance au SL (risque contournement)
        if direction.upper() == "BUY":
            dist_tp1 = tp1 - current_price
            dist_sl = current_price - sl
        else:
            dist_tp1 = current_price - tp1
            dist_sl = sl - current_price
        dist_tp1 = round(dist_tp1, 1)
        dist_sl = round(dist_sl, 1)
        risk_sl = " ⚠️ Proche SL" if dist_sl <= 5 else ""

        if gain_pts < min_gain_for_be:
            msg = (
                "📌 Zone de consolidation — Infos clés\n\n"
                f"💰 Prix: {_p(current_price)} | Entrée: {_p(entry)}\n"
                f"🎯 {dist_tp1:.1f} pts jusqu'au TP1 | {dist_sl:.1f} pts jusqu'au SL {risk_sl}\n\n"
                "Trade en cours, plan inchangé. Option: réduire le SL si risque de contournement élevé."
            )
        else:
            msg = (
                "💰 Gain actuel +{:.1f} pts — Zone de consolidation\n\n"
                f"Prix: {_p(current_price)} | Entrée: {_p(entry)} | SL: {_p(sl)} | TP1: {_p(tp1)}\n"
                f"🎯 {dist_tp1:.1f} pts jusqu'au TP1 | {dist_sl:.1f} pts jusqu'au SL\n\n"
                "Option: sécuriser en BE/partiel pour figer le gain, ou maintenir vers TP1."
            ).format(gain_pts)

        return SuiviResult(
            status="ALERTE",
            message=msg,
            closed=False,
        )

    # --- MAINTIEN : uniquement si TOUS les critères OK ---
    news_imminent = _is_news_high_imminent(news_state)
    if news_imminent:
        return SuiviResult(
            status="ALERTE",
            message=(
                f"📰 News HIGH imminente\n\n"
                f"Prix: {_p(current_price)} | SL: {_p(sl)} | TP1: {_p(tp1)}\n\n"
                f"Option: passer en BE ou partiel pour sécuriser avant la news."
            ),
            closed=False,
        )

    # Tous les critères OK : MAINTIEN
    prefix = "🟦 MAINTIEN BUY" if direction.upper() == "BUY" else "🟥 MAINTIEN SELL"
    return SuiviResult(
        status="MAINTIEN",
        message=(
            f"{prefix}\n\n"
            f"💰 Prix: {_p(current_price)} | Entrée: {_p(entry)}\n"
            f"🎯 SL: {_p(sl)} | TP1: {_p(tp1)} | TP2: {_p(tp2)}\n\n"
            f"Structure OK, objectif TP maintenu."
        ),
        closed=False,
    )


def _get_suivi_verdict(
    direction: str,
    entry: float,
    current_price: float,
    structure_h1: str,
    structure_m15_ok: bool,
) -> str:
    """Verdict encourageant et informatif — confiance dans le trade, options claires."""
    if direction.upper() == "BUY":
        gain_pts = current_price - entry
    else:
        gain_pts = entry - current_price
    gain_pts = round(gain_pts, 1)
    h1_avec_nous = (
        (direction.upper() == "BUY" and structure_h1 == "BULLISH")
        or (direction.upper() == "SELL" and structure_h1 == "BEARISH")
    )
    if gain_pts >= 5 and structure_m15_ok and h1_avec_nous:
        return "🚀 On avance vers TP1, laisser courir."
    if gain_pts >= 0 and structure_m15_ok:
        return "📈 Prix dans le bon sens."
    if not structure_m15_ok and gain_pts >= 5:
        return "💰 Gain en place. Option: BE/partiel pour sécuriser ou maintenir."
    if not structure_m15_ok and gain_pts >= 0:
        return "📊 M15 en consolidation. Plan inchangé."
    if not structure_m15_ok and gain_pts < 0:
        return "📊 M15 en consolidation. Option: BE si marge, sinon maintenir."
    if not h1_avec_nous and structure_h1 != "RANGE":
        return "⚡ H1 contre. Plan inchangé."
    return "⏳ Pas encore de marge BE. Laisser courir."


def compute_suivi_situation_signature(
    direction: str,
    entry: float,
    current_price: float,
    structure_h1: str,
    structure_m15_ok: bool,
    analysis_summary: str,
) -> str:
    """
    Signature de la situation pour anti-spam : structure_m15_ok | analyse | verdict.
    Si identique au dernier envoi, on ne renvoie pas le message.
    """
    verdict = _get_suivi_verdict(direction, entry, current_price, structure_h1, structure_m15_ok)
    return f"{structure_m15_ok}|{analysis_summary}|{verdict}"


def build_suivi_situation_message(
    direction: str,
    entry: float,
    current_price: float,
    tp1: float,
    sl: float,
    structure_h1: str,
    structure_m15_ok: bool,
    duration_min: int,
    score_total: Optional[int] = None,
    analysis_summary: str = "",
    recommendation: str = "",
) -> str:
    """
    Message de situation suivi : durée, prix vs entrée, tendance H1/M15, score, analyse, verdict.
    Envoyé au plus toutes les 2 min. N'envoie que si la situation a changé (anti-spam).
    """
    if direction.upper() == "BUY":
        gain_pts = current_price - entry
    else:
        gain_pts = entry - current_price
    gain_pts = round(gain_pts, 1)
    if gain_pts >= 0:
        pts_str = f"+{gain_pts:.1f} pts"
    else:
        pts_str = f"{gain_pts:.1f} pts"

    h1_avec_nous = (
        (direction.upper() == "BUY" and structure_h1 == "BULLISH")
        or (direction.upper() == "SELL" and structure_h1 == "BEARISH")
    )
    if structure_h1 == "RANGE":
        h1_label = "H1: RANGE (neutre)"
    elif h1_avec_nous:
        h1_label = f"H1: {structure_h1} (avec nous)"
    else:
        h1_label = f"H1: {structure_h1} (contre tendance)"

    m15_label = "M15: structure OK" if structure_m15_ok else "M15: consolidation"
    verdict = _get_suivi_verdict(direction, entry, current_price, structure_h1, structure_m15_ok)

    lines = [
        f"📊 Suivi — Trade actif depuis {duration_min} min",
        "",
        f"Prix: {_p(current_price)} | Entrée: {_p(entry)} | {pts_str}",
        f"SL: {_p(sl)} | TP1: {_p(tp1)}",
        "",
        f"{h1_label} | {m15_label}",
    ]
    if score_total is not None:
        lines.append("")
        lines.append(f"Score marché: {score_total}/100")
    if analysis_summary:
        lines.append("")
        lines.append(f"Analyse: {analysis_summary}")
    if recommendation:
        lines.append("")
        lines.append(f"💡 {recommendation}")
    lines.append("")
    lines.append(verdict)
    return "\n".join(lines)
