# CHANGELOG

## Sprint 2 Polishing
- Mock XAUUSD pricing adjusted to realistic 46xx range and SL/TP spacing updated.
- Added `score_effective` to decision output and DB logging, with NO_GO forced to 0.
- Formatter clarified: GO shows score, NO_GO shows market score + reason.
- DATA_OFF now uses clean reasons ("Données marché indisponibles") only.
- FastAPI startup migrated to lifespan handler (remove `on_event` warnings).

## Sprint 2.5
- Telegram sender (GO + NO_GO importants) avec anti-spam par signal_key.
- Logging Telegram ajouté dans `signals` (sent/error/latency).
- Tests Telegram + README pour création bot et `chat_id`.
- Script `scripts/telegram_setup.py` + endpoint `/telegram/test` protégé par `ADMIN_TOKEN`.

## Sprint 2.6
- Docker Compose charge désormais les secrets via `.env.local`.
- Script Telegram: écriture par défaut dans `.env.local` uniquement (option .env = opt-in).
- README: section Secrets (dev vs prod).

## Sprint 2.9
- MT5 Bridge skeleton (FastAPI stub) + remote MT5 provider HTTP.
- DATA_OFF si bridge down ou data trop ancienne.
- README + .env.example mis à jour.

## Sprint 3.0
- Coach IA (OpenAI) pour messages Telegram + suivi coûts.
- News timing (moment + horizon) et pré-alertes.
 - Tables ai_usage_daily + ai_messages, endpoint /coach/preview.
