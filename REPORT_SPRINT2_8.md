# REPORT_SPRINT2_8

## Résumé
- Status: **PASS**
- News provider externe + Context agent optionnel

## Changements clés
- News provider HTTP avec cache TTL 5 min, retry, timeout court.
- Context provider HTTP avec cache TTL 5 min, retry, timeout court.
- DecisionPacket enrichi (`sources_used`, `context_summary`).
- README + .env.example mis à jour.

## Tests
```
docker compose run --rm -w /app -e PYTHONPATH=/app api pytest -q
```
