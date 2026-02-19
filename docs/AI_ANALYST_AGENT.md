# AI Analyst Agent — Couche d'analyse et d'apprentissage

## Objectif

Agent IA **isolé** qui observe le système de trading, analyse les résultats, calcule les performances et propose des améliorations du code — **sans jamais modifier le flux de trading**.

## Principes

- **Lecture seule** : lit signals, outcomes, config. Ne touche jamais aux décisions GO/NO_GO.
- **Couche à part** : exécuté manuellement ou en fin de journée via endpoint admin.
- **Apprentissage** : accumule les patterns (setup_type, blocked_by, win rate) pour affiner les recommandations.

## Données utilisées

| Source | Contenu |
|--------|---------|
| `signals` | GO/NO_GO, blocked_by, score, direction, entry, sl, tp1, setup (via packet) |
| `meta.trade_outcomes_{day}` | PnL par trade clôturé (pips signés) |
| Config (résumé) | SL_MIN/MAX, TP1, GO_MIN_SCORE, STATE_MACHINE_ENABLED, etc. |

## Sorties

1. **Résumé jour/semaine** : analyse count, GO count, outcomes, total pips, win rate
2. **Patterns** : blocages fréquents (EXTENSION_MOVE, NEWS_LOCK…), setup_type performants
3. **Recommandations** : améliorations code avec justification (ex. "Réduire SL à 12 quand ATR<18")
4. **Insights trading** : apprentissage (ex. "PULLBACK_SR +70% cette semaine")

## Déclenchement

- `POST /admin/analyst-run?days=7` — exécution manuelle
- **Planifié** : exécution automatique entre 23h00 et 00h00 Paris (marché fermé)
  - Script : `python -m app.scripts.analyst_daily_run`
  - Installer : `.\scripts\install_analyst_task.ps1` (crée une tâche Windows à 23h00)

## Stockage

- Rapport dans `meta.ai_analyst_report_{ts}` (JSON)
- Dernier rapport : `meta.ai_analyst_last_report`

## Intégration

- Utilise `generate_coach_message` (OpenAI) comme les autres agents
- Respecte `ai_max_cost_eur_per_day`
- Optionnel : envoi résumé sur Telegram
