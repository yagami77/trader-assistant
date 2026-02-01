# REPORT_SPRINT2_6

## Résumé
- Status: **PASS**
- Objectif: secrets Telegram via `.env.local` uniquement

## Changements clés
- `docker-compose.yml` charge `.env.local` (plus de dépendance à `.env`).
- `scripts/telegram_setup.py` n'écrit plus `.env` par défaut (opt-in).
- README enrichi avec section **Secrets**.

## Tests
```
docker compose run --rm -w /app -e PYTHONPATH=/app api pytest -q
```

## Vérification manuelle
```
docker compose up -d --build
curl http://localhost:8000/health
curl -X POST http://localhost:8000/telegram/test \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"text":"Test Telegram ✅"}'
```
