"""
Agent Analyste IA — couche isolée qui observe, analyse et recommande.
Ne modifie jamais le flux de trading. Lit signals, outcomes, config.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from app.config import get_settings
from app.infra.db import (
    get_analyst_outcomes_by_day,
    get_analyst_signals,
    save_analyst_report,
)
from app.infra.openai_client import generate_analyst_message


@dataclass(frozen=True)
class AnalystResult:
    summary: str
    recommendations: List[str]
    raw_response: str
    input_tokens: int
    output_tokens: int


def _build_config_summary() -> str:
    """Résumé des paramètres clés (sans secrets)."""
    s = get_settings()
    return (
        f"SL: {getattr(s, 'sl_min_pts', 20)}-{getattr(s, 'sl_max_pts', 25)} pts | "
        f"TP1: {getattr(s, 'tp1_min_pts', 7)}-{getattr(s, 'tp1_max_pts', 15)} | "
        f"GO_MIN_SCORE: {getattr(s, 'go_min_score', 80)} | "
        f"STATE_MACHINE: {getattr(s, 'state_machine_enabled', False)} | "
        f"M15_FETCH_BARS: {getattr(s, 'm15_fetch_bars', 80)} | "
        f"IMPULSE: ATR*{getattr(s, 'impulse_atr_mult', 1.8)}, retest_tol={getattr(s, 'impulse_retest_tolerance_atr', 0.35)}"
    )


def _build_analyst_prompt(signals: List[Dict], outcomes_by_day: Dict[str, List[float]], days: int) -> str:
    """Construit le prompt pour l'IA analyste."""
    config = _build_config_summary()
    n_go = sum(1 for s in signals if str(s.get("status", "")).upper() == "GO")
    n_no_go = len(signals) - n_go
    blocked_counts: Dict[str, int] = {}
    for s in signals:
        b = s.get("blocked_by") or "GO"
        blocked_counts[b] = blocked_counts.get(b, 0) + 1

    outcomes_flat: List[float] = []
    for day, vals in outcomes_by_day.items():
        outcomes_flat.extend(vals)
    total_pips = round(sum(outcomes_flat), 1) if outcomes_flat else 0.0
    wins = sum(1 for v in outcomes_flat if v > 0)
    win_rate = round(100 * wins / len(outcomes_flat), 1) if outcomes_flat else 0.0

    prompt = f"""Tu es un analyste trading expert. Tu observes un système de signaux (GO/NO_GO) sur XAUUSD M15.

## Paramètres actuels
{config}

## Données des {days} derniers jours
- Analyses: {len(signals)} (GO: {n_go}, NO_GO: {n_no_go})
- Blocages: {dict(blocked_counts)}
- Trades clôturés: {len(outcomes_flat)}, total pips: {total_pips}, win rate: {win_rate}%

## Échantillon des 15 derniers signaux
"""
    for s in signals[-15:]:
        st = s.get("status", "?")
        bl = s.get("blocked_by", "-")
        sc = s.get("score_total", "?")
        setup = s.get("setup_type", "?")
        prompt += f"- {s.get('ts_utc', '')[:16]} {st} blocked_by={bl} score={sc} setup={setup}\n"

    if outcomes_flat:
        prompt += f"\n## Outcomes (pips): {outcomes_flat}\n"

    prompt += """
Tu dois être GÉNÉREUX. Utilise des emojis (💰📉📈✅❌🔧) et des retours à la ligne (\\n).

PRIORITÉ 1 : Profit et Perte
- Combien de profit total (pts) et combien de pertes (pts)
- Analyser les pertes : POURQUOI ? (SL touché, structure cassée, entrée tardive, setup faible...)
- Qu'est-ce qu'il faut améliorer suite à ça ?

Réponds en JSON:
{
  "summary": "Section RÉSULTAT FINANCIER en premier (profit, perte, bilan). Puis ANALYSE DES PERTES (pourquoi, causes). Puis blocages. Utilise \\n pour les retours à la ligne et des emojis.",
  "recommendations": ["Recommandation 1 : POURQUOI et COMMENT améliorer", "Recommandation 2..."],
  "insights": "Insights détaillés : quoi améliorer, conseils concrets."
}
"""

    return prompt


_BLOCAGE_LABELS = {
    "DATA_OFF": "Données marché indisponibles (bridge MT5 déconnecté ou latence)",
    "DUPLICATE_SIGNAL": "Cooldown actif — éviter les doublons après un GO récent",
    "SPREAD_TOO_HIGH": "Spread trop élevé — coûts d'entrée trop importants",
    "OUT_OF_SESSION": "Hors fenêtre de trading (marché fermé vendredi 23h → lundi 00h)",
    "EXTENSION_MOVE": "Prix trop loin de la structure — entrée tardive évitée",
    "NO_SETUP": "Aucun setup détecté ou score insuffisant",
    "RR_TOO_LOW": "Risk-Reward trop faible pour le TP1",
    "NEWS_LOCK": "News à fort impact imminente — pas de trade",
    "SETUP_NOT_CONFIRMED": "Setup non confirmé (timing, barres de confirmation)",
    "LOW_LIQUIDITY": "Heures creuses — trading limité (fenêtre 0h–22h Paris, 23h fermeture)",
    "ROOM_TO_TARGET": "TP1 trop proche d'un niveau S/R — pas assez de room",
    "STATE_MACHINE_NOT_READY": "State machine en attente",
    "GO": "Signal GO envoyé",
}


def _build_fallback_summary(
    signals: List[Dict], outcomes_by_day: Dict[str, List[float]], days: int
) -> AnalystResult:
    """Résumé détaillé : profit/perte en tête, analyse des pertes, recommandations."""
    n_go = sum(1 for s in signals if str(s.get("status", "")).upper() == "GO")
    n_no_go = len(signals) - n_go
    blocked_counts: Dict[str, int] = {}
    for s in signals:
        b = str(s.get("blocked_by") or "GO")
        blocked_counts[b] = blocked_counts.get(b, 0) + 1

    outcomes_flat: List[float] = []
    for day, vals in outcomes_by_day.items():
        outcomes_flat.extend(vals)

    wins = [v for v in outcomes_flat if v > 0]
    loss_list = [v for v in outcomes_flat if v < 0]
    total_profit = round(sum(wins), 1) if wins else 0.0
    total_loss = round(sum(loss_list), 1) if loss_list else 0.0  # négatif
    total_pips = round(total_profit + total_loss, 1)
    n_wins = len(wins)
    n_losses = len(loss_list)
    win_rate = round(100 * n_wins / len(outcomes_flat), 1) if outcomes_flat else 0.0
    avg_win = round(total_profit / n_wins, 1) if n_wins else 0.0
    avg_loss = round(total_loss / n_losses, 1) if n_losses else 0.0

    pct_go = round(100 * n_go / len(signals), 1) if signals else 0
    top_blocked = sorted(blocked_counts.items(), key=lambda x: -x[1])[:6]

    parts: List[str] = []
    parts.append("📅 Période analysée : {} jours".format(days))
    parts.append("")
    parts.append("═══════════════════════")
    parts.append("💰 RÉSULTAT FINANCIER")
    parts.append("═══════════════════════")
    parts.append("")
    parts.append("📈 Profit total : +{:.1f} pts ({} trades gagnants)".format(total_profit, n_wins))
    parts.append("")
    parts.append("📉 Perte totale : {:.1f} pts ({} trades perdants)".format(total_loss, n_losses))
    parts.append("")
    parts.append("💵 BILAN : {} pts".format(total_pips))
    if total_pips > 0:
        parts.append("   ✅ Rentable sur la période")
    elif total_pips < 0:
        parts.append("   ❌ Déficitaire — voir recommandations")
    parts.append("")
    parts.append("📊 Win rate : {}% | Moyenne gain : +{} pts | Moyenne perte : {} pts".format(
        win_rate, avg_win, avg_loss
    ))
    parts.append("")
    parts.append("───────────────────────")
    parts.append("📋 Analyse des pertes")
    parts.append("───────────────────────")
    parts.append("")
    if n_losses > 0:
        parts.append("Les {} pertes ({} pts) viennent souvent de :".format(n_losses, total_loss))
        parts.append("")
        parts.append("• SL touché — prix est parti contre nous")
        parts.append("  (structure cassée, entrée tardive, ou setup faible)")
        parts.append("")
        parts.append("• Moyenne perte = {} pts par trade perdant".format(avg_loss))
        if avg_win > 0 and abs(avg_loss) > 0:
            rr_effectif = round(avg_win / abs(avg_loss), 1)
            parts.append("")
            parts.append("• Ratio gain/perte = {:.1f} (gain moyen {}x la perte moyenne)".format(
                rr_effectif, rr_effectif
            ))
            if rr_effectif < 1:
                parts.append("  ⚠️ Les pertes sont plus grosses que les gains — risque mal calibré")
    else:
        parts.append("✅ Aucune perte sur la période")
    parts.append("")
    parts.append("───────────────────────")
    parts.append("🚫 Principaux blocages")
    parts.append("───────────────────────")
    parts.append("")
    for k, v in top_blocked:
        if k == "GO":
            continue
        label = _BLOCAGE_LABELS.get(k, k)
        pct = round(100 * v / len(signals), 1) if signals else 0
        parts.append("• {} ({}x, {}%)".format(k, v, pct))
        parts.append("  {}\n".format(label))
    parts.append("")
    parts.append("📊 Analyses : {} total | {} GO ({}%) | {} NO_GO".format(
        len(signals), n_go, pct_go, n_no_go
    ))

    summary = "\n".join(parts)

    recs: List[str] = []
    if n_losses > 0 and total_pips < 0:
        recs.append(
            "🔴 PnL négatif : les pertes dépassent les gains.\n"
            "→ Revoir le SL (trop serré = stop souvent) ou le TP1 (objectif trop loin).\n"
            "→ Envisager GO_MIN_SCORE plus élevé pour ne prendre que les meilleurs setups."
        )
    elif n_losses > 0 and avg_win < abs(avg_loss):
        recs.append(
            "⚠️ Les pertes moyennes sont plus grandes que les gains.\n"
            "→ Soit resserrer le SL pour limiter les pertes, soit viser un TP1 plus loin pour augmenter les gains."
        )
    if blocked_counts.get("EXTENSION_MOVE", 0) > 10:
        recs.append(
            "EXTENSION_MOVE fréquent ({}x) : entrées bloquées car prix trop loin de la structure.\n"
            "→ Augmenter IMPULSE_RETEST_TOLERANCE_ATR (0.35 → 0.45) pour accepter plus de retests.".format(
                blocked_counts.get("EXTENSION_MOVE", 0)
            )
        )
    if blocked_counts.get("DATA_OFF", 0) > len(signals) * 0.3:
        recs.append(
            "DATA_OFF dominant ({}%) : données souvent indisponibles.\n"
            "→ Vérifier connexion MT5, DATA_MAX_AGE_SEC, stabilité du bridge.".format(
                round(100 * blocked_counts.get("DATA_OFF", 0) / len(signals), 1)
            )
        )
    if n_go == 0 and n_no_go > 20:
        recs.append(
            "Aucun GO : tout est bloqué.\n"
            "→ Revoir GO_MIN_SCORE, fenêtres de trading, ou blocages dominants."
        )
    if total_pips > 0 and not recs:
        recs.append("✅ Période rentable. Continuer sur la même stratégie.")
    if not recs:
        recs.append("Aucune recommandation spécifique — données insuffisantes.")

    return AnalystResult(
        summary=summary,
        recommendations=recs,
        raw_response="",
        input_tokens=0,
        output_tokens=0,
    )


def run_analyst(days: int = 7, save_report: bool = True) -> AnalystResult:
    """
    Lance l'analyse IA. Lit les données, appelle OpenAI, retourne le résultat.
    Si OpenAI échoue (401, etc.), fallback sur un résumé basique sans IA.
    """
    settings = get_settings()
    signals = get_analyst_signals(days=days)
    outcomes_by_day = get_analyst_outcomes_by_day(days=days)

    if not getattr(settings, "openai_api_key", ""):
        fallback = _build_fallback_summary(signals, outcomes_by_day, days)
        if save_report:
            save_analyst_report(
                json.dumps(
                    {"summary": fallback.summary, "recommendations": fallback.recommendations, "days": days},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return fallback

    prompt = _build_analyst_prompt(signals, outcomes_by_day, days)
    try:
        result = generate_analyst_message(prompt)
    except Exception:
        fallback = _build_fallback_summary(signals, outcomes_by_day, days)
        if save_report:
            save_analyst_report(
                json.dumps(
                    {"summary": fallback.summary, "recommendations": fallback.recommendations, "days": days},
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return fallback

    raw = result.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        summary = parsed.get("summary", raw[:500])
        recommendations = parsed.get("recommendations", [])
        if not isinstance(recommendations, list):
            recommendations = [str(recommendations)]
        if save_report:
            save_analyst_report(
                json.dumps(
                    {
                        "summary": summary,
                        "recommendations": recommendations,
                        "insights": parsed.get("insights", ""),
                        "days": days,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return AnalystResult(
            summary=summary,
            recommendations=recommendations,
            raw_response=raw,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
    except json.JSONDecodeError:
        return AnalystResult(
            summary=raw[:800] if len(raw) > 800 else raw,
            recommendations=[],
            raw_response=raw,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
