# DATA_OFF — Règles pour éviter les régressions

## Quand DATA_OFF est déclenché

1. **build_decision_packet() lève une exception** (bridge MT5 injoignable, timeout, etc.)  
   → Retries : 3 tentatives avec 2 s entre chaque (erreurs bridge/connection/timeout/mt5).

2. **Données trop anciennes**  
   → `packet.data_latency_ms > DATA_MAX_AGE_SEC * 1000`  
   → La latence est calculée sur la **bougie la plus récente** (`candles_m15[0]`), pas la plus ancienne.

## Règle critique : DATA_MAX_AGE_SEC et TF_SIGNAL

- **TF_SIGNAL=M15** : une bougie = 15 min. La bougie la plus récente peut avoir **0 à 15 min**.
- Si `DATA_MAX_AGE_SEC=120` (2 min) → DATA_OFF quasi permanent.
- **Minimum recommandé pour M15 : 900** (15 min). Défaut dans le code : **960** (16 min).
- Le `config` applique un **minimum 900** quand `TF_SIGNAL=M15` pour éviter une config incohérente.

## Fichiers concernés

- `app/config.py` : `data_max_age_sec`, garde-fou M15.
- `app/agents/decision_packet.py` : `data_latency_ms` = âge de **candles_m15[0]** (bougie la plus récente).
- `app/api/main.py` : utilisation de `data_off`, retries, seuil « Data trop ancienne ».

## Évolution future

- Ne pas utiliser `candles_m15[-1]` pour la latence (c’est l’ancienne bougie).
- Ne pas mettre `DATA_MAX_AGE_SEC` < 900 avec M15.
- Toute modification du flux DATA_OFF doit tenir compte de ces deux points.
