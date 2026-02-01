# REPORT_SPRINT3_COACH

## Résumé
- Status: **PASS**
- Coach Telegram OpenAI + budget journalier + preview admin

## Changements clés
- Client OpenAI mockable avec timeout/retry.
- CoachAgent: budget max en EUR/jour + coût estimé.
- News timing: moment + horizon + pré-alertes.
- Tables `ai_usage_daily` et `ai_messages`.
- Endpoint `/coach/preview` sécurisé.

## Tests
```
docker compose run --rm -w /app -e PYTHONPATH=/app -v /Users/admin/Desktop/trader-assistant:/app api pytest -q
```
