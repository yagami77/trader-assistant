"""
Moteur SUIVI — après un GO, suit le trade jusqu'à TP ou SL.
MAINTIEN / ALERTE (retournement, résistance, patterns contre) / SORTIE (TP ou SL atteint).
Logique qualitative marché : structure M15, S/R, pin bar/engulfing contre, news HIGH imminente.
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
    """Message SORTIE SL (via bougies)."""
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


def _msg_tp2(entry: float, tp2: float, price_touched: float, direction: str) -> str:
    """Message SORTIE TP2 (via bougies)."""
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


def _candles_since(candles: List[dict], started_ts_iso: Optional[str]) -> List[dict]:
    """Filtre les bougies depuis le début du trade (started_ts_iso). Toujours triées par temps croissant."""
    if not candles:
        return candles
    # Tri chronologique même sans filtre (MT5 renvoie newest-first)
    _ts = lambda c: int(c.get("time") or c.get("time_msc") or 0) if (c.get("time") or c.get("time_msc")) else 0
    if not started_ts_iso:
        out = list(candles)
        out.sort(key=_ts)
        return out
    try:
        from datetime import datetime, timezone
        start_dt = datetime.fromisoformat(started_ts_iso)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        start_sec = start_dt.timestamp()
    except (ValueError, TypeError):
        out = list(candles)
        out.sort(key=_ts)
        return out
    out = []
    for c in candles:
        t = c.get("time") or c.get("time_msc")
        if t is None:
            continue
        ts = int(t) if int(t) < 1e12 else int(t) // 1000
        if ts >= start_sec - 60:  # -60 s marge (bougie en cours)
            out.append(c)
    out.sort(key=_ts)
    return out if out else candles


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
) -> SuiviResult:
    """
    Évalue le suivi du trade actif (logique qualitative marché).
    - SORTIE: TP1, TP2 ou SL atteint
    - ALERTE: au moins un signal (S/R proche, cassure structure, pin bar/engulfing contre, stagnation)
    - MAINTIEN: uniquement si TOUS les critères OK (structure M15 valide, pas S/R proche,
      pas de pattern contre, pas de news HIGH imminente)
    """
    news_state = news_state or {}
    struct_m15 = analyze_structure(candles_m15) if candles_m15 else None
    last_hl = struct_m15.last_swing_low if struct_m15 else None
    last_lh = struct_m15.last_swing_high if struct_m15 else None
    sr_levels = struct_m15.sr_levels if struct_m15 else []

    # --- SORTIE : prix actuel OU high/low de la DERNIÈRE bougie uniquement ---
    # On ne regarde plus toutes les anciennes bougies, seulement la dernière en cours (comme le suivi live).
    candles_since = _candles_since(candles_m15 or [], active_started_ts)
    last_candle = candles_since[-1] if candles_since else (candles_m15[-1] if candles_m15 else None)
    if last_candle:
        h = float(last_candle.get("high", 0))
        l_ = float(last_candle.get("low", 0))
        if direction.upper() == "BUY":
            if h >= tp1:
                pts = round(tp1 - entry, 2)
                return SuiviResult(status="SORTIE", message=_msg_tp1(entry, tp1, h, direction), closed=True, outcome_pips=pts)
            if h >= tp2:
                pts = round(tp2 - entry, 2)
                return SuiviResult(status="SORTIE", message=_msg_tp2(entry, tp2, h, direction), closed=True, outcome_pips=pts)
        else:
            if l_ <= tp1:
                pts = round(entry - tp1, 2)
                return SuiviResult(status="SORTIE", message=_msg_tp1(entry, tp1, l_, direction), closed=True, outcome_pips=pts)
            if l_ <= tp2:
                pts = round(entry - tp2, 2)
                return SuiviResult(status="SORTIE", message=_msg_tp2(entry, tp2, l_, direction), closed=True, outcome_pips=pts)

    # --- SORTIE : prix actuel (si pas déjà détecté via bougies) ---
    if direction.upper() == "BUY":
        if current_price <= sl:
            pts = round(entry - sl, 2)
            return SuiviResult(
                status="SORTIE",
                message=(
                    f"😔 SL touché — trade raté\n\n"
                    f"📊 Résultat du trade: PERTE — {pts:.1f} point\n\n"
                    f"Prix: {_p(current_price)} | SL: {_p(sl)}\n"
                    f"On va récupérer dans la journée, on va faire mieux !\n"
                    f"Trade clôturé. Prochaine opportunité."
                ),
                closed=True,
                outcome_pips=-pts,
            )
        if current_price >= tp1:
            pts = round(tp1 - entry, 2)
            return SuiviResult(
                status="SORTIE",
                message=(
                    f"🎉 Bravo ! TP1 atteint\n\n"
                    f"📊 Résultat du trade: PROFIT +{pts:.1f} point\n\n"
                    f"Prix: {_p(current_price)} | TP1: {_p(tp1)}\n"
                    f"Objectif principal atteint. À la prochaine !"
                ),
                closed=True,
                outcome_pips=pts,
            )
    else:
        if current_price >= sl:
            pts = round(sl - entry, 2)
            return SuiviResult(
                status="SORTIE",
                message=(
                    f"😔 SL touché — trade raté\n\n"
                    f"📊 Résultat du trade: PERTE — {pts:.1f} point\n\n"
                    f"Prix: {_p(current_price)} | SL: {_p(sl)}\n"
                    f"On va récupérer dans la journée, on va faire mieux !\n"
                    f"Trade clôturé. Prochaine opportunité."
                ),
                closed=True,
                outcome_pips=-pts,
            )
        if current_price <= tp1:
            pts = round(entry - tp1, 2)
            return SuiviResult(
                status="SORTIE",
                message=(
                    f"🎉 Bravo ! TP1 atteint\n\n"
                    f"📊 Résultat du trade: PROFIT +{pts:.1f} point\n\n"
                    f"Prix: {_p(current_price)} | TP1: {_p(tp1)}\n"
                    f"Objectif principal atteint. À la prochaine !"
                ),
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

        if gain_pts < min_gain_for_be:
            # Très proche de l'entrée : on signale juste le mur, sans demander BE
            msg = (
                "⚠️ ALERTE — Mur / faiblesse proche\n\n"
                f"Prix: {_p(current_price)} | Entrée: {_p(entry)} | SL: {_p(sl)} | TP1: {_p(tp1)}\n"
                "Surveiller le trade, zone sensible, mais pas encore de marge pour passer BE."
            )
        else:
            # En gain suffisant : recommandation de sécurisation (BE / partiel)
            msg = (
                "⚠️ ALERTE — Attention mur / faiblesse\n\n"
                f"Prix: {_p(current_price)} | Entrée: {_p(entry)} | SL: {_p(sl)} | TP1: {_p(tp1)}\n"
                f"Gain actuel ≈ {gain_pts:.1f} pts — sécurisation conseillée (BE / partiel)."
            )

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
                f"⚠️ ALERTE — News HIGH imminente\n\n"
                f"Prix: {_p(current_price)} | SL: {_p(sl)} | TP1: {_p(tp1)}\n"
                f"Sécurisation conseillée (BE / partiel)."
            ),
            closed=False,
        )

    # Tous les critères OK : MAINTIEN
    prefix = "🛫🟦 MAINTIEN BUY" if direction.upper() == "BUY" else "📉🟥 MAINTIEN SELL"
    return SuiviResult(
        status="MAINTIEN",
        message=(
            f"{prefix}\n\n"
            f"Prix: {_p(current_price)} | Entrée: {_p(entry)}\n"
            f"SL: {_p(sl)} | TP1: {_p(tp1)} | TP2: {_p(tp2)}\n"
            f"Plan inchangé, structure OK, pas de mur proche, objectif TP maintenu."
        ),
        closed=False,
    )


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
    Envoyé au plus toutes les 5 min. Si situation changée, inclut une recommandation (fermer / accepter dégâts).
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

    m15_label = "M15: structure OK" if structure_m15_ok else "M15: cassure / faiblesse"

    if gain_pts >= 5 and structure_m15_ok and h1_avec_nous:
        verdict = "On va vers TP1, laisser courir."
    elif gain_pts >= 0 and structure_m15_ok:
        verdict = "Prix dans le bon sens, surveiller."
    elif not structure_m15_ok and gain_pts < 0:
        verdict = "Pas favorable, envisager sortie ou BE si possible."
    elif not structure_m15_ok:
        verdict = "Structure M15 à surveiller."
    elif not h1_avec_nous and structure_h1 != "RANGE":
        verdict = "Contre tendance H1, rester vigilant."
    else:
        verdict = "Surveiller, pas encore de marge pour BE."

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
        lines.append(f"Recommandation: {recommendation}")
    lines.append("")
    lines.append(f"➡️ {verdict}")
    return "\n".join(lines)
