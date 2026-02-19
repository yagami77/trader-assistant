# Grille de scoring — Référence

Score total **0–100** en 3 blocs. **Ni strict ni perdant** : critères à 0 pt quand non remplis, pas de pénalités négatives (sauf règle critique Edge < 28 → plafond 85).

---

## Règle globale

- **Edge < 28** → score total plafonné à **85** (setup non joué en GO).
- Sinon : score = Edge + Qualité entrée + Risk & Execution.

---

## Mode TREND (H1 = UP ou DOWN)

| Bloc | Critère | Pts | Si non rempli |
|------|---------|-----|----------------|
| **EDGE (max 40)** | Market Phase alignée (IMPULSE/PULLBACK) | +10 | 0 pt (ou +5 si non évaluée, 0 si CONSOLIDATION) |
| | Structure H1 claire (HH/HL ou LH/LL) | +10 | 0 pt |
| | Breakout validé | +8 | 0 pt |
| | Room to target valide | +6 | 0 pt |
| | Momentum M15 confirmé | +4 | 0 pt |
| | Fibo confluence (si activé) | +2 à +3 | 0 pt |
| | *Cap si CONSOLIDATION* | — | Edge max 25 |
| **QUALITÉ ENTRÉE (max 30)** | Pullback ratio (zone 25–55 %) | +10 | 0 pt |
| | Rejet M5 clair | +8 | 0 pt |
| | timing_ready | +6 | 0 pt |
| | Pas d’extension excessive | +6 | 0 pt (pas de pénalité) |
| **RISK & EXECUTION (max 30)** | RR TP1 ≥ seuil | +10 | 0 pt |
| | Spread ≤ spread_max | +6 | 0 pt |
| | ATR ≤ atr_max | +6 | 0 pt |
| | SL cohérent (SL_MIN_PTS – SL_MAX_PTS) | +8 | 0 pt |

---

## Mode RANGE (H1 = RANGE)

| Bloc | Critère | Pts | Si non rempli |
|------|---------|-----|----------------|
| **EDGE (max 40)** | Mode RANGE (H1 range) | — | (ligne d’info) |
| | Rejet borne extrême | +10 | 0 pt |
| | Sweep high/low | +8 | 0 pt |
| | Break structure interne | +8 | 0 pt |
| | Volume spike | +6 | 0 pt |
| | Breakout validé | +4 | 0 pt |
| | Room to target valide | +4 | 0 pt |
| **QUALITÉ ENTRÉE (max 30)** | *(identique au mode Trend)* | | |
| **RISK & EXECUTION (max 30)** | *(identique au mode Trend)* | | |

---

## Résumé

- **Strict** : on ne donne des points que si le critère est rempli.
- **Non perdant** : 0 pt si non rempli, jamais de retrait de points (sauf plafond Edge < 28).
- **Correct et rempli** : chaque case a une règle claire ; Risk & Execution identique en Trend et en Range.

Pour que le mode Range score sur rejet borne / sweep / break structure / volume spike, il faut remplir le `state` du packet avec : `range_rejet_borne`, `range_sweep`, `range_break_structure`, `range_volume_spike` (booléens).
