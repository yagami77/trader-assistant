# Trader Assistant (Sprint 2.5)

## Démarrage rapide
- `docker compose up -d --build`
- API: `http://localhost:8000/health`

## Telegram (GO + NO_GO importants)
### Créer un bot
1) Ouvrir Telegram et chercher **@BotFather**.
2) Envoyer `/newbot` et suivre les étapes.
3) Récupérer le **token** fourni.

### Obtenir le chat_id
1) Créer un groupe Telegram et ajouter le bot.
2) Envoyer un message dans le groupe.
3) Lire l’ID via l’API:
   - `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - repérer `chat.id`

### Setup automatique (recommandé)
1) Créer un groupe Telegram.
2) Ajouter le bot **@Yagami77Signal_bot**.
3) Écrire `test` dans le groupe.
4) Lancer: `python scripts/telegram_setup.py`
5) Le script écrit **.env.local** (non versionné).
6) Tester: 
   - `curl -X POST http://localhost:8000/telegram/test -H "X-Admin-Token: <ADMIN_TOKEN>" -H "Content-Type: application/json" -d '{"text":"Test Telegram ✅"}'`

### Secrets
- **DEV**: utiliser `.env.local` (non versionné).
- **PROD**: variables d’environnement via panel VPS ou secrets Docker.

## News + Context (Sprint 2.8)
### News API (TradingEconomics)
Variables:
- `NEWS_PROVIDER=tradingeconomics|calendar_api|api|mock`
- `TE_BASE_URL=https://api.tradingeconomics.com`
- `TE_API_KEY=guest:guest` (test limite)
- `NEWS_COUNTRIES=united states` (csv)
- `NEWS_IMPORTANCE_MIN=2` (2=medium, 3=high)
- `NEWS_LOOKAHEAD_HOURS=24`
- `NEWS_LOCK_HIGH_PRE_MIN=20`
- `NEWS_LOCK_HIGH_POST_MIN=10`
- `NEWS_LOCK_MED_PRE_MIN=10`
- `NEWS_LOCK_MED_POST_MIN=5`
- `NEWS_CACHE_TTL_SEC=300`
- `NEWS_TIMEOUT_SEC=4`
- `NEWS_RETRY=1`
- `NEWS_FALLBACK_TO_MOCK=true`
- `NEWS_PREALERT_MINUTES=60,30,15`

Script de verification:
```
docker compose run --rm -w /app api bash scripts/check_news_provider.sh
```

Debug rapide:
```
curl http://localhost:8000/news/next
```

### News Impact (module)
- Module separé qui ajoute `news_impact_summary` dans le DecisionPacket.
- Regles deterministes simples (pas d'IA) pour indiquer l'impact possible sur l'or.

## Coach IA (OpenAI)
Variables:
- `AI_ENABLED=true|false`
- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-4o-mini`
- `AI_TIMEOUT_SEC=6`
- `AI_PRICE_INPUT_PER_1M`
- `AI_PRICE_OUTPUT_PER_1M`
- `AI_MAX_COST_EUR_PER_DAY=1.0`
- `AI_MAX_TOKENS_PER_MESSAGE=800`
- `COACH_LANGUAGE=fr`
- `COACH_MODE=pro`
- `FX_EURUSD=1.08`

Endpoint coût/jour:
```
curl -H "X-Admin-Token: <ADMIN_TOKEN>" "http://localhost:8000/stats/ai_cost?date=YYYY-MM-DD"
```

Preview (sans envoi Telegram):
```
curl -X POST http://localhost:8000/coach/preview \
  -H "X-Admin-Token: <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD"}'
```

### Context API (optionnel)
Variables:
- `CONTEXT_ENABLED=true|false`
- `CONTEXT_API_BASE_URL`
- `CONTEXT_API_KEY` (option)

## Deploy MT5 Bridge (Windows VPS)
1) Installer Python 3.11 sur le VPS Windows.
2) (Optionnel) Installer MetaTrader5 Python lib pour la vraie intégration.
3) Lancer le bridge:
   - `python -m uvicorn services.mt5_bridge.main:app --host 0.0.0.0 --port 5005`
4) Configurer l’API principale:
   - `MARKET_PROVIDER=remote_mt5`
   - `MT5_BRIDGE_URL=http://<VPS_IP>:5005`

### Remote MT5 (tests rapides)
```
curl http://137.74.116.242:8000/health
curl "http://137.74.116.242:8000/tick?symbol=XAUUSD"
curl "http://137.74.116.242:8000/spread?symbol=XAUUSD"
curl "http://137.74.116.242:8000/candles?symbol=XAUUSD&timeframe=M15&count=10"
curl "http://137.74.116.242:8000/candles?symbol=XAUUSD&tf=M15&n=10"
```

### Lancer le core avec MT5 Bridge
```
MARKET_PROVIDER=remote_mt5 MT5_BRIDGE_URL=http://137.74.116.242:8000 docker compose up -d --build
```

### Exemple `.env.local`
```
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABCDEF
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_SEND_NO_GO_IMPORTANT=true
TELEGRAM_NO_GO_IMPORTANT_BLOCKS=NEWS_LOCK,DATA_OFF,DAILY_BUDGET_REACHED
ADMIN_TOKEN=change_me
NEWS_PROVIDER=mock
NEWS_API_BASE_URL=
NEWS_API_KEY=
NEWS_LOCK_MIN=30
CONTEXT_ENABLED=false
CONTEXT_API_BASE_URL=
CONTEXT_API_KEY=
MARKET_PROVIDER=mock
MT5_BRIDGE_URL=
DATA_MAX_AGE_SEC=120
```

## Tests
- `docker compose run --rm -w /app -e PYTHONPATH=/app -v /Users/admin/Desktop/trader-assistant:/app api pytest -q`


