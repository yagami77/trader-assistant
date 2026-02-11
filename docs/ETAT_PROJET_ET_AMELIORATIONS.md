# État du projet Trader Assistant — récapitulatif et pistes d’amélioration

Document de référence pour voir tout ce qui est en place et identifier des améliorations.

---

## 1. Objectif et périmètre

- **Instrument** : XAUUSD, **signal M15**, **contexte H1**.
- **Produit** : signaux et alertes dans un **groupe Telegram** (pas d’app dédiée). Pas d’exécution automatique des ordres (V1).
- **Risque** : 1 % par défaut, 2 % si signal **A+** (score ≥ 90). Budget perte/jour configurable.
- **TP/SL** : 2 TP — TP1 (50 % + SL à l’entrée), TP2 (reste). Suivi jusqu’à SORTIE (TP1, TP2 ou SL).

---

## 2. Architecture actuelle

### 2.1 Stack

- **API** : FastAPI (`app/api/main.py`), port 8081.
- **Données** : provider abstrait (Mock ou Remote MT5 via bridge HTTP).
- **Bridge MT5** : `services/mt5_bridge` (FastAPI, port 8080), appelle MT5 pour tick, bougies, spread.
- **Base** : SQLite (`signals`, `state`, `meta`, `ai_usage_daily`, etc.).
- **Runner** : boucle qui appelle `POST /analyze` à intervalle fixe (ex. 60 s). Option `--once` pour un seul cycle.

### 2.2 Modules principaux

| Dossier / Fichier | Rôle |
|-------------------|------|
| `app/agents/decision_packet.py` | Construit le DecisionPacket (bougies M15/H1, structure, bias, setups, entry/SL/TP, news, spread, ATR, state). |
| `app/agents/news_agent.py` | Verrou news (lock actif, prochain événement). |
| `app/agents/news_impact_agent.py` | Résumé d’impact news pour le packet. |
| `app/agents/coach_agent.py` | Prompt et sortie Coach IA (message Telegram enrichi). |
| `app/engines/hard_rules.py` | Règles bloquantes : session, news, spread, SL max, RR TP1, budget, cooldown, setup confirmé. |
| `app/engines/scorer.py` | Score 0–100 et liste de raisons avec points (grille détaillée). |
| `app/engines/setup_engine.py` | Détection des setups (BREAKOUT_RETEST, PULLBACK_SR, etc.) et calcul entry/SL/TP1/TP2 (mode scalp). |
| `app/engines/structure_engine.py` | Structure M15 (swing high/low, niveaux S/R). |
| `app/engines/entry_timing_engine.py` | Timing d’entrée (zone, rejet, momentum M15). |
| `app/engines/suivi_engine.py` | Suivi post-GO : MAINTIEN / ALERTE / SORTIE (TP1, TP2, SL). Détection sur **dernière bougie** + prix actuel. |
| `app/engines/news_timing.py` | Moment et horizon des news (pré-alerte, lock). |
| `app/infra/formatter.py` | Format des messages Telegram (GO avec détail score, NO_GO avec blocage + **détails du score**). |
| `app/infra/telegram_sender.py` | Envoi des messages vers Telegram. |
| `app/infra/db.py` | SQLite : signals, state, meta, suivi (trade actif, SORTIE envoyée une fois par trade), outcomes, etc. |
| `app/config.py` | Configuration via variables d’environnement (.env.local ou NSSM). |
| `app/state_repo.py` | Lecture/écriture state (jour, perte, cooldown, setup en cours). |

---

## 3. Règles métier implémentées

### 3.1 Hard rules (bloquantes)

- **OUT_OF_SESSION** : hors fenêtre trading (configurable : fenêtres ou market_close).
- **NEWS_LOCK** : news high impact dans la fenêtre (news_state lock_active).
- **SPREAD_TOO_HIGH** : spread > spread_max ou ratio spread/risque trop élevé, ou hard spread max.
- **SL_TOO_LARGE** : distance SL > sl_max_pts.
- **VOLATILITY_TOO_HIGH** : ATR > atr_max.
- **RR_TOO_LOW** : RR TP1 < rr_min (ou rr_hard_min_tp1 en bloc fort).
- **DAILY_BUDGET_REACHED** : perte du jour ≥ budget.
- **DUPLICATE_SIGNAL** : cooldown non écoulé (last_ts + cooldown_minutes).
- **SETUP_NOT_CONFIRMED** : pas assez de barres de confirmation (setup_confirm_min_bars).
- **DATA_OFF** : provider injoignable ou données trop anciennes (data_max_age_sec, ex. 960 s pour M15).

Pas de **NO_TREND_BIAS** en blocage dur actuellement : H1 contre = 0 pt au score, pas de bloc.

### 3.2 Grille de score (scorer.py)

- **Confluence H1** : +10 si aligné, 0 si contre (pas de pénalité).
- **Setup clair** : +25 si au moins un setup détecté.
- **RR TP1** : +20 si ≥ rr_min, sinon raison sans points.
- **Spread** : +10 si ≤ spread_max, pénalité soft -1 à -5 si > soft_spread_start_pts.
- **Volatilité** : +10 si ATR ≤ atr_max.
- **News** : +10 si pas de news_lock.
- **Bon moment** : +10 si timing_ready (zone/rejet).
- **Setup pro** : +5 si BREAKOUT_RETEST ou PULLBACK_SR.
- **Momentum M15** : +10 si aligné, -15 si contre.

Seuils (configurables) : **GO si score ≥ go_min_score** (défaut 80), **A+ si score ≥ a_plus_min_score** (défaut 90). En prod on impose souvent **GO_MIN_SCORE=90** pour n’envoyer que des A+ sur Telegram.

### 3.3 Décision GO / NO_GO

- Si **DATA_OFF** → NO_GO (blocked_by DATA_OFF).
- Sinon **hard rules** évaluées ; si une bloque → NO_GO + blocked_by.
- Sinon si **score_total < go_min_score** → NO_GO (Score insuffisant).
- Sinon si **timing non prêt** et **setup_confirm_count < setup_confirm_min_bars** → NO_GO (SETUP_NOT_CONFIRMED).
- Sinon → **GO**. Qualité A+ si score ≥ a_plus_min_score, sinon A.

**Safeguard Telegram** : on n’envoie un GO sur Telegram **que si** score_total ≥ a_plus_min_score (évite d’envoyer un GO « A » par erreur de config).

### 3.4 Suivi (après un GO envoyé)

- **Trade actif** : stocké en base (entry, sl, tp1, tp2, direction, active_started_ts).
- **SORTIE** : détection sur **dernière bougie M15** (high/low) + **prix actuel** ; **TP1 prioritaire** sur TP2. SL uniquement via prix actuel.
- Message **« Bravo TP1 atteint »** (ou TP2/SL) envoyé **une seule fois par trade** (marqueur en base par active_started_ts).
- **ALERTE** : structure M15 contre, S/R proche, chandelles contre, news HIGH imminente → un message alerte par trade (avec délai après démarrage).
- **MAINTIEN** : message situation possible à mi-chemin TP (une fois par trade).
- Résumé du jour (optionnel) en fin de session (heure Paris configurable).

### 3.5 Telegram

- **GO** : message avec prix actuel, entrée, SL, TP1, TP2, SUIVI, qualité A+, score, **détails du score** (grille complète).
- **NO_GO** : bloqué par + raison courte + **score global** + **détails du score** (pour voir ce qui a pénalisé).
- **NO_GO « importants »** : liste configurable (ex. NEWS_LOCK, DATA_OFF, DAILY_BUDGET_REACHED, RR_TOO_LOW, SETUP_NOT_CONFIRMED, SL_TOO_LARGE) avec cooldown pour éviter le spam.
- **SORTIE** : Bravo TP1 / TP2 / SL avec résultat en points.
- **Clôture manuelle** : `POST /trade/manual-close` enregistre le résultat et envoie le message.
- **DATA_OFF** : alerte « données indisponibles » ; quand les données reviennent, message « données de retour ».

---

## 4. API et déploiement

### 4.1 Endpoints principaux

- **GET /health** : statut API.
- **POST /analyze** : analyse complète (packet, hard rules, score, décision, suivi si trade actif, envoi Telegram si règles d’envoi remplies).
- **GET /data-status** : données marché OK ou non (bridge, latence, DATA_OFF).
- **GET /stats/summary** : résumé du jour (n_go, n_no_go, outcomes_pips, total_pips, budget).
- **GET /stats/ai_cost** : coût IA par jour (admin).
- **GET /news/next** : prochain événement news, lock, fenêtre.
- **POST /coach/preview** : aperçu message Coach (admin).
- **POST /trade/manual-close** : clôture manuelle + envoi résultat Telegram (admin).
- **POST /admin/reset-active-trade** : efface le trade actif (script restart, admin).
- **POST /telegram/test** : test envoi Telegram (admin).

### 4.2 Config (.env.local / NSSM)

- **Seuils** : GO_MIN_SCORE, A_PLUS_MIN_SCORE (ex. 90 pour n’avoir que des A+).
- **Marché** : MARKET_PROVIDER, MT5_BRIDGE_URL, DATA_MAX_AGE_SEC (≥ 900 pour M15).
- **Session** : TRADING_SESSION_MODE, MARKET_CLOSE_START/END, ALWAYS_IN_SESSION (dev).
- **News** : NEWS_PROVIDER, TE_BASE_URL, TE_API_KEY, pays, importance, fenêtres lock/prealert.
- **Telegram** : TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_SEND_NO_GO_IMPORTANT, TELEGRAM_NO_GO_IMPORTANT_BLOCKS.
- **Suivi** : SR_BUFFER_POINTS, SUIVI_ALERTE_INTERVAL_MINUTES, SUIVI_SITUATION_INTERVAL_MINUTES, COOLDOWN_AFTER_TRADE_MINUTES.
- **IA** : AI_ENABLED, OPENAI_API_KEY, OPENAI_MODEL, AI_TIMEOUT_SEC, COACH_LANGUAGE, COACH_MODE.

### 4.3 Scripts Windows (NSSM)

- **restart_prod.ps1** : init DB, nettoyage __pycache__, redémarrage mt5-bridge, trader-core, trader-runner, health check, reset trade actif. Force **GO_MIN_SCORE=90** et **A_PLUS_MIN_SCORE=90** pour trader-core (AppEnvironmentExtra NSSM).
- **install_mt5_bridge_nssm.ps1** : installation service mt5-bridge.
- **install_runner_nssm.ps1** : installation service trader-runner.

---

## 5. Ce qui n’est pas fait ou partiel (par rapport à la spec)

- **Table `trades`** (sync MT5) : non implémentée ; pas de POST /trade/sync.
- **NO_TREND_BIAS** en hard rule : spec dit « setup contre bias => NO_GO » ; actuellement H1 contre = 0 pt seulement.
- **Fenêtres de session** : spec 14:30–18:30 et option 20:00–22:00 ; en prod mode market_close (23:00–00:05) ou fenêtres custom.
- **IA décisionnelle** (override GO/NO_GO) : spec V1.1 ; actuellement Coach enrichit le message mais la décision reste 100 % règles + score (pas d’appel IA pour décision binaire).
- **Coach batch V2** : analyse quotidienne signaux vs outcomes, table coach_reports, pas implémenté.
- **EXECUTION_GUARD** : spec (prix trop loin de l’entrée) non implémenté en hard rule.
- **Calcul du lot** (risque / (distance_SL × valeur_point)) : mentionné dans le message Telegram / spec, pas calculé ni affiché automatiquement dans l’API.

---

## 6. Pistes d’amélioration

### 6.1 Fiabilité et prod

- **Vérifier chargement .env.local** en prod (répertoire de travail du service NSSM, chemin absolu dans main.py) pour que GO_MIN_SCORE / A_PLUS_MIN_SCORE soient bien lus.
- **Retry / backoff** : analyse en cas de DATA_OFF temporaire (déjà partiel avec retry bridge).
- **Logs structurés** : niveau, correlation_id ou signal_key pour tracer une décision de bout en bout.
- **Health du bridge** : endpoint dédié ou data-status utilisé par un monitoring.

### 6.2 Score et filtrage

- **A/B test seuils** : tester GO_MIN_SCORE 85 vs 90 sur une période (avec historique des signaux).
- **Pondération dynamique** : ajuster les points (ex. momentum M15) selon volatilité ou régime H1.
- **NO_TREND_BIAS** : réintroduire en hard rule si tu veux « jamais de GO contre H1 » (au lieu de seulement 0 pt).

### 6.3 Suivi

- **Détection SORTIE** : actuellement dernière bougie + prix actuel ; possible d’ajouter un délai min après ouverture pour éviter faux TP1 sur la première bougie.
- **Alertes** : seuils ou conditions supplémentaires (ex. distance au SL en points) pour affiner les alertes.
- **Résumé du jour** : inclure nombre de GO envoyés, nombre de SORTIE TP1/TP2/SL.

### 6.4 Telegram et UX

- **Résumé score NO_GO** : déjà en place (détails du score en bas) ; possible d’ajouter une ligne « Manque X pt pour GO » si proche du seuil.
- **Format GO** : rappel du risque 1 % / 2 % et formule lot (optionnel, si tu veux tout dans le message).
- **Pré-alerte news** : déjà en place ; possibilité d’ajuster les minutes (60, 30, 15) ou les messages.

### 6.5 Données et backtest

- **Historique signals** : exporter (CSV/JSON) pour analyse hors ligne ou backtest.
- **Table trades** + **POST /trade/sync** : lier signaux et résultats MT5 pour stats réelles (winrate, expectancy).
- **DATA_OFF** : métriques (nombre d’occurrences par jour, durée) pour surveiller la stabilité du bridge.

### 6.6 Code et tests

- **Tests Telegram** : certains tests (ex. envoi NO_GO important, duplicate) à realigner avec le comportement actuel (blocked_by, should_send).
- **Tests suivi_engine** : scénarios avec dernière bougie (high/low) et prix actuel pour TP1/TP2/SL.
- **Config** : documenter toutes les variables dans un seul fichier (ex. docs/CONFIG.md) avec défaut et impact.

### 6.7 Spec et évolutions

- **EXECUTION_GUARD** : bloquer si le prix s’est trop éloigné de l’entry (slippage / entrée tardive).
- **Session** : fenêtres 14:30–18:30 et 20:00–22:00 en option (déjà partiellement flexible via config).
- **Coach V2** : rapport quotidien automatique (signaux, outcomes, recommandations).

---

## 7. Fichiers clés à garder en tête

| Fichier | Rôle |
|---------|------|
| `app/api/main.py` | Point d’entrée analyse, suivi, envoi Telegram, décision, DB. |
| `app/engines/scorer.py` | Grille de score et raisons. |
| `app/engines/hard_rules.py` | Blocages. |
| `app/engines/suivi_engine.py` | Logique SORTIE/ALERTE/MAINTIEN. |
| `app/infra/formatter.py` | Texte GO/NO_GO Telegram. |
| `app/agents/decision_packet.py` | Construction du packet (données marché + state). |
| `app/config.py` | Toute la config. |
| `deploy/windows/restart_prod.ps1` | Redémarrage prod et force GO_MIN_SCORE=90. |

Tu peux t’appuyer sur ce document pour prioriser les prochaines améliorations (fiabilité, score, suivi, Telegram, données, tests ou spec).
