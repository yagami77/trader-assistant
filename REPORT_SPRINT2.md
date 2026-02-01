# REPORT_SPRINT2

## Résumé
- Status: **PASS**
- API port détecté: `8000`
- /health: `{"status": "ok"}`

## Tests unitaires
```
............                                                             [100%]
=============================== warnings summary ===============================
tests/test_api.py::test_health
  /app/app/api/main.py:30: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

tests/test_api.py::test_health
  /usr/local/lib/python3.11/site-packages/fastapi/applications.py:4495: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 2 warnings in 6.79s
```

## Scénarios E2E
- Toutes les lectures DB utilisent `ORDER BY id DESC LIMIT N`.
### OUT_OF_SESSION
Réponse:
```json
{
  "decision": {
    "status": "NO_GO",
    "blocked_by": "OUT_OF_SESSION",
    "score_total": 100,
    "score_effective": 0,
    "confidence": 100,
    "quality": "A+",
    "why": [
      "Hors fenêtre de trading"
    ]
  },
  "message": "NO GO ❌ XAUUSD (M15)\nBloqué par : OUT_OF_SESSION — Hors fenêtre de trading\nScore marché : 100/100",
  "decision_packet": {
    "session_ok": false,
    "news_lock": false,
    "news_next_event": {
      "datetime_iso": "2026-01-21T16:00:00+01:00",
      "impact": "HIGH",
      "title": "FOMC Minutes"
    },
    "spread": 12.0,
    "spread_max": 20.0,
    "atr": 1.1,
    "atr_max": 2.0,
    "bias_h1": "UP",
    "setups_detected": [
      "Breakout+Retest",
      "Rejet S/R",
      "Pullback Tendance",
      "Range Propre"
    ],
    "proposed_entry": 4672.0,
    "sl": 4642.0,
    "tp1": 4702.0,
    "tp2": 4747.0,
    "rr_tp2": 2.5,
    "rr_min": 2.0,
    "score_rules": 100,
    "reasons_rules": [
      "Bias H1 aligné",
      "Setup clair",
      "RR TP2 >= 2.0",
      "Spread OK",
      "Volatilité OK",
      "News OK"
    ],
    "state": {
      "daily_budget_used": 0.0,
      "cooldown_ok": true,
      "last_signal_key": null,
      "consecutive_losses": 0
    },
    "timestamps": {
      "ts_utc": "2026-01-21T08:00:00+00:00",
      "ts_paris": "2026-01-21T09:00:00+01:00"
    },
    "data_latency_ms": 15
  },
  "ai_output": null,
  "ai_enabled": false,
  "data_latency_ms": 15,
  "ai_latency_ms": null,
  "signal_key": "a7eb2b2a191eca8e48cec6ab82ade5c6a1f89ab2"
}
```
DB (dernieres lignes):
```json
[
  {
    "status": "NO_GO",
    "blocked_by": "OUT_OF_SESSION",
    "score_total": 100,
    "score_effective": 0,
    "decision_packet_json": "{\"session_ok\": false, \"news_lock\": false, \"news_next_event\": {\"datetime_iso\": \"2026-01-21T16:00:00+01:00\", \"impact\": \"HIGH\", \"title\": \"FOMC Minutes\"}, \"spread\": 12.0, \"spread_max\": 20.0, \"atr\": 1.1, \"atr_max\": 2.0, \"bias_h1\": \"UP\", \"setups_detected\": [\"Breakout+Retest\", \"Rejet S/R\", \"Pullback Tendance\", \"Range Propre\"], \"proposed_entry\": 4672.0, \"sl\": 4642.0, \"tp1\": 4702.0, \"tp2\": 4747.0, \"rr_tp2\": 2.5, \"rr_min\": 2.0, \"score_rules\": 100, \"reasons_rules\": [\"Bias H1 align\\u00e9\", \"Setup clair\", \"RR TP2 >= 2.0\", \"Spread OK\", \"Volatilit\\u00e9 OK\", \"News OK\"], \"state\": {\"daily_budget_used\": 0.0, \"cooldown_ok\": true, \"last_signal_key\": null, \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-21T08:00:00+00:00\", \"ts_paris\": \"2026-01-21T09:00:00+01:00\"}, \"data_latency_ms\": 15}"
  }
]
```

### NEWS_LOCK
Réponse:
```json
{
  "decision": {
    "status": "NO_GO",
    "blocked_by": "NEWS_LOCK",
    "score_total": 90,
    "score_effective": 0,
    "confidence": 90,
    "quality": "A+",
    "why": [
      "News high impact"
    ]
  },
  "message": "NO GO ❌ XAUUSD (M15)\nBloqué par : NEWS_LOCK — News high impact\nScore marché : 90/100",
  "decision_packet": {
    "session_ok": true,
    "news_lock": true,
    "news_next_event": {
      "datetime_iso": "2026-01-21T14:55:00+00:00",
      "impact": "HIGH",
      "title": "TEST NEWS"
    },
    "spread": 12.0,
    "spread_max": 20.0,
    "atr": 1.1,
    "atr_max": 2.0,
    "bias_h1": "UP",
    "setups_detected": [
      "Breakout+Retest",
      "Rejet S/R",
      "Pullback Tendance",
      "Range Propre"
    ],
    "proposed_entry": 4672.0,
    "sl": 4642.0,
    "tp1": 4702.0,
    "tp2": 4747.0,
    "rr_tp2": 2.5,
    "rr_min": 2.0,
    "score_rules": 90,
    "reasons_rules": [
      "Bias H1 aligné",
      "Setup clair",
      "RR TP2 >= 2.0",
      "Spread OK",
      "Volatilité OK"
    ],
    "state": {
      "daily_budget_used": 0.0,
      "cooldown_ok": true,
      "last_signal_key": null,
      "consecutive_losses": 0
    },
    "timestamps": {
      "ts_utc": "2026-01-21T14:45:00+00:00",
      "ts_paris": "2026-01-21T15:45:00+01:00"
    },
    "data_latency_ms": 15
  },
  "ai_output": null,
  "ai_enabled": false,
  "data_latency_ms": 15,
  "ai_latency_ms": null,
  "signal_key": "bb091d9d279dd9bbe051c9ef34a5d958f34bc518"
}
```
DB (dernieres lignes):
```json
[
  {
    "status": "NO_GO",
    "blocked_by": "NEWS_LOCK",
    "score_total": 90,
    "score_effective": 0,
    "decision_packet_json": "{\"session_ok\": true, \"news_lock\": true, \"news_next_event\": {\"datetime_iso\": \"2026-01-21T14:55:00+00:00\", \"impact\": \"HIGH\", \"title\": \"TEST NEWS\"}, \"spread\": 12.0, \"spread_max\": 20.0, \"atr\": 1.1, \"atr_max\": 2.0, \"bias_h1\": \"UP\", \"setups_detected\": [\"Breakout+Retest\", \"Rejet S/R\", \"Pullback Tendance\", \"Range Propre\"], \"proposed_entry\": 4672.0, \"sl\": 4642.0, \"tp1\": 4702.0, \"tp2\": 4747.0, \"rr_tp2\": 2.5, \"rr_min\": 2.0, \"score_rules\": 90, \"reasons_rules\": [\"Bias H1 align\\u00e9\", \"Setup clair\", \"RR TP2 >= 2.0\", \"Spread OK\", \"Volatilit\\u00e9 OK\"], \"state\": {\"daily_budget_used\": 0.0, \"cooldown_ok\": true, \"last_signal_key\": null, \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-21T14:45:00+00:00\", \"ts_paris\": \"2026-01-21T15:45:00+01:00\"}, \"data_latency_ms\": 15}"
  }
]
```

### DUPLICATE_SIGNAL (1st)
Réponse:
```json
{
  "decision": {
    "status": "GO",
    "blocked_by": null,
    "score_total": 100,
    "score_effective": 100,
    "confidence": 100,
    "quality": "A+",
    "why": [
      "Bias H1 aligné",
      "Setup clair",
      "RR TP2 >= 2.0"
    ]
  },
  "message": "GO ✅ XAUUSD (M15)\n\nDirection : BUY\nEntrée : 4672.0\nStop Loss : 4642.0\nTP1 : 4702.0 → Prendre 50% + Mettre SL = Entrée\nTP2 : 4747.0 → Prendre le reste\n\nPourquoi : Bias H1 aligné + Setup clair + RR TP2 >= 2.0\nScore : 100/100 — Qualité : A+",
  "decision_packet": {
    "session_ok": true,
    "news_lock": false,
    "news_next_event": {
      "datetime_iso": "2026-01-21T16:00:00+01:00",
      "impact": "HIGH",
      "title": "FOMC Minutes"
    },
    "spread": 12.0,
    "spread_max": 20.0,
    "atr": 1.1,
    "atr_max": 2.0,
    "bias_h1": "UP",
    "setups_detected": [
      "Breakout+Retest",
      "Rejet S/R",
      "Pullback Tendance",
      "Range Propre"
    ],
    "proposed_entry": 4672.0,
    "sl": 4642.0,
    "tp1": 4702.0,
    "tp2": 4747.0,
    "rr_tp2": 2.5,
    "rr_min": 2.0,
    "score_rules": 100,
    "reasons_rules": [
      "Bias H1 aligné",
      "Setup clair",
      "RR TP2 >= 2.0",
      "Spread OK",
      "Volatilité OK",
      "News OK"
    ],
    "state": {
      "daily_budget_used": 0.0,
      "cooldown_ok": true,
      "last_signal_key": null,
      "consecutive_losses": 0
    },
    "timestamps": {
      "ts_utc": "2026-01-21T09:00:00+00:00",
      "ts_paris": "2026-01-21T10:00:00+01:00"
    },
    "data_latency_ms": 15
  },
  "ai_output": null,
  "ai_enabled": false,
  "data_latency_ms": 15,
  "ai_latency_ms": null,
  "signal_key": "400f639cb5505a9ce916b522297df15873a09753"
}
```
DB (dernieres lignes):
```json
[
  {
    "status": "NO_GO",
    "blocked_by": "DUPLICATE_SIGNAL",
    "score_total": 100,
    "score_effective": 0,
    "decision_packet_json": "{\"session_ok\": true, \"news_lock\": false, \"news_next_event\": {\"datetime_iso\": \"2026-01-21T16:00:00+01:00\", \"impact\": \"HIGH\", \"title\": \"FOMC Minutes\"}, \"spread\": 12.0, \"spread_max\": 20.0, \"atr\": 1.1, \"atr_max\": 2.0, \"bias_h1\": \"UP\", \"setups_detected\": [\"Breakout+Retest\", \"Rejet S/R\", \"Pullback Tendance\", \"Range Propre\"], \"proposed_entry\": 4672.0, \"sl\": 4642.0, \"tp1\": 4702.0, \"tp2\": 4747.0, \"rr_tp2\": 2.5, \"rr_min\": 2.0, \"score_rules\": 100, \"reasons_rules\": [\"Bias H1 align\\u00e9\", \"Setup clair\", \"RR TP2 >= 2.0\", \"Spread OK\", \"Volatilit\\u00e9 OK\", \"News OK\"], \"state\": {\"daily_budget_used\": 0.0, \"cooldown_ok\": false, \"last_signal_key\": \"400f639cb5505a9ce916b522297df15873a09753\", \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-21T09:00:00+00:00\", \"ts_paris\": \"2026-01-21T10:00:00+01:00\"}, \"data_latency_ms\": 15}"
  }
]
```

### DUPLICATE_SIGNAL (2nd)
Réponse:
```json
{
  "decision": {
    "status": "NO_GO",
    "blocked_by": "DUPLICATE_SIGNAL",
    "score_total": 100,
    "score_effective": 0,
    "confidence": 100,
    "quality": "A+",
    "why": [
      "Cooldown actif"
    ]
  },
  "message": "NO GO ❌ XAUUSD (M15)\nBloqué par : DUPLICATE_SIGNAL — Cooldown actif\nScore marché : 100/100",
  "decision_packet": {
    "session_ok": true,
    "news_lock": false,
    "news_next_event": {
      "datetime_iso": "2026-01-21T16:00:00+01:00",
      "impact": "HIGH",
      "title": "FOMC Minutes"
    },
    "spread": 12.0,
    "spread_max": 20.0,
    "atr": 1.1,
    "atr_max": 2.0,
    "bias_h1": "UP",
    "setups_detected": [
      "Breakout+Retest",
      "Rejet S/R",
      "Pullback Tendance",
      "Range Propre"
    ],
    "proposed_entry": 4672.0,
    "sl": 4642.0,
    "tp1": 4702.0,
    "tp2": 4747.0,
    "rr_tp2": 2.5,
    "rr_min": 2.0,
    "score_rules": 100,
    "reasons_rules": [
      "Bias H1 aligné",
      "Setup clair",
      "RR TP2 >= 2.0",
      "Spread OK",
      "Volatilité OK",
      "News OK"
    ],
    "state": {
      "daily_budget_used": 0.0,
      "cooldown_ok": false,
      "last_signal_key": "400f639cb5505a9ce916b522297df15873a09753",
      "consecutive_losses": 0
    },
    "timestamps": {
      "ts_utc": "2026-01-21T09:00:00+00:00",
      "ts_paris": "2026-01-21T10:00:00+01:00"
    },
    "data_latency_ms": 15
  },
  "ai_output": null,
  "ai_enabled": false,
  "data_latency_ms": 15,
  "ai_latency_ms": null,
  "signal_key": "400f639cb5505a9ce916b522297df15873a09753"
}
```
DB (dernieres lignes):
```json
[
  {
    "status": "NO_GO",
    "blocked_by": "DUPLICATE_SIGNAL",
    "score_total": 100,
    "score_effective": 0,
    "decision_packet_json": "{\"session_ok\": true, \"news_lock\": false, \"news_next_event\": {\"datetime_iso\": \"2026-01-21T16:00:00+01:00\", \"impact\": \"HIGH\", \"title\": \"FOMC Minutes\"}, \"spread\": 12.0, \"spread_max\": 20.0, \"atr\": 1.1, \"atr_max\": 2.0, \"bias_h1\": \"UP\", \"setups_detected\": [\"Breakout+Retest\", \"Rejet S/R\", \"Pullback Tendance\", \"Range Propre\"], \"proposed_entry\": 4672.0, \"sl\": 4642.0, \"tp1\": 4702.0, \"tp2\": 4747.0, \"rr_tp2\": 2.5, \"rr_min\": 2.0, \"score_rules\": 100, \"reasons_rules\": [\"Bias H1 align\\u00e9\", \"Setup clair\", \"RR TP2 >= 2.0\", \"Spread OK\", \"Volatilit\\u00e9 OK\", \"News OK\"], \"state\": {\"daily_budget_used\": 0.0, \"cooldown_ok\": false, \"last_signal_key\": \"400f639cb5505a9ce916b522297df15873a09753\", \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-21T09:00:00+00:00\", \"ts_paris\": \"2026-01-21T10:00:00+01:00\"}, \"data_latency_ms\": 15}"
  },
  {
    "status": "GO",
    "blocked_by": null,
    "score_total": 100,
    "score_effective": 100,
    "decision_packet_json": "{\"session_ok\": true, \"news_lock\": false, \"news_next_event\": {\"datetime_iso\": \"2026-01-21T16:00:00+01:00\", \"impact\": \"HIGH\", \"title\": \"FOMC Minutes\"}, \"spread\": 12.0, \"spread_max\": 20.0, \"atr\": 1.1, \"atr_max\": 2.0, \"bias_h1\": \"UP\", \"setups_detected\": [\"Breakout+Retest\", \"Rejet S/R\", \"Pullback Tendance\", \"Range Propre\"], \"proposed_entry\": 4672.0, \"sl\": 4642.0, \"tp1\": 4702.0, \"tp2\": 4747.0, \"rr_tp2\": 2.5, \"rr_min\": 2.0, \"score_rules\": 100, \"reasons_rules\": [\"Bias H1 align\\u00e9\", \"Setup clair\", \"RR TP2 >= 2.0\", \"Spread OK\", \"Volatilit\\u00e9 OK\", \"News OK\"], \"state\": {\"daily_budget_used\": 0.0, \"cooldown_ok\": true, \"last_signal_key\": null, \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-21T09:00:00+00:00\", \"ts_paris\": \"2026-01-21T10:00:00+01:00\"}, \"data_latency_ms\": 15}"
  }
]
```

### DUPLICATE_SIGNAL (counts)
Réponse:
```json
{
  "before": 0,
  "after_first": 1,
  "after_second": 2
}
```
DB (dernieres lignes):
```json
[]
```

### RR_TOO_LOW
Réponse:
```json
{
  "decision": {
    "status": "NO_GO",
    "blocked_by": "RR_TOO_LOW",
    "score_total": 80,
    "score_effective": 0,
    "confidence": 80,
    "quality": "A",
    "why": [
      "RR TP2 insuffisant"
    ]
  },
  "message": "NO GO ❌ XAUUSD (M15)\nBloqué par : RR_TOO_LOW — RR TP2 insuffisant\nScore marché : 80/100",
  "decision_packet": {
    "session_ok": true,
    "news_lock": false,
    "news_next_event": null,
    "spread": 12.0,
    "spread_max": 20.0,
    "atr": 1.1,
    "atr_max": 2.0,
    "bias_h1": "UP",
    "setups_detected": [
      "Breakout+Retest",
      "Rejet S/R",
      "Pullback Tendance",
      "Range Propre"
    ],
    "proposed_entry": 4672.0,
    "sl": 4642.0,
    "tp1": 4702.0,
    "tp2": 4747.0,
    "rr_tp2": 2.5,
    "rr_min": 10.0,
    "score_rules": 80,
    "reasons_rules": [
      "Bias H1 aligné",
      "Setup clair",
      "Spread OK",
      "Volatilité OK",
      "News OK"
    ],
    "state": {
      "daily_budget_used": 0.0,
      "cooldown_ok": true,
      "last_signal_key": null,
      "consecutive_losses": 0
    },
    "timestamps": {
      "ts_utc": "2026-01-22T08:16:16.300577+00:00",
      "ts_paris": "2026-01-22T09:16:16.300577+01:00"
    },
    "data_latency_ms": 15
  },
  "ai_output": null,
  "ai_enabled": false,
  "data_latency_ms": 15,
  "ai_latency_ms": null,
  "signal_key": "b8a0af07426fac6950cf7a3fa2c1c9e9671fa036"
}
```
DB (dernieres lignes):
```json
[
  {
    "status": "NO_GO",
    "blocked_by": "RR_TOO_LOW",
    "score_total": 80,
    "score_effective": 0,
    "decision_packet_json": "{\"session_ok\": true, \"news_lock\": false, \"news_next_event\": null, \"spread\": 12.0, \"spread_max\": 20.0, \"atr\": 1.1, \"atr_max\": 2.0, \"bias_h1\": \"UP\", \"setups_detected\": [\"Breakout+Retest\", \"Rejet S/R\", \"Pullback Tendance\", \"Range Propre\"], \"proposed_entry\": 4672.0, \"sl\": 4642.0, \"tp1\": 4702.0, \"tp2\": 4747.0, \"rr_tp2\": 2.5, \"rr_min\": 10.0, \"score_rules\": 80, \"reasons_rules\": [\"Bias H1 align\\u00e9\", \"Setup clair\", \"Spread OK\", \"Volatilit\\u00e9 OK\", \"News OK\"], \"state\": {\"daily_budget_used\": 0.0, \"cooldown_ok\": true, \"last_signal_key\": null, \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-22T08:16:16.300577+00:00\", \"ts_paris\": \"2026-01-22T09:16:16.300577+01:00\"}, \"data_latency_ms\": 15}"
  }
]
```

### DAILY_BUDGET_REACHED
Réponse:
```json
{
  "decision": {
    "status": "NO_GO",
    "blocked_by": "DAILY_BUDGET_REACHED",
    "score_total": 100,
    "score_effective": 0,
    "confidence": 100,
    "quality": "A+",
    "why": [
      "Budget journalier atteint"
    ]
  },
  "message": "NO GO ❌ XAUUSD (M15)\nBloqué par : DAILY_BUDGET_REACHED — Budget journalier atteint\nScore marché : 100/100",
  "decision_packet": {
    "session_ok": true,
    "news_lock": false,
    "news_next_event": {
      "datetime_iso": "2026-01-21T16:00:00+01:00",
      "impact": "HIGH",
      "title": "FOMC Minutes"
    },
    "spread": 12.0,
    "spread_max": 20.0,
    "atr": 1.1,
    "atr_max": 2.0,
    "bias_h1": "UP",
    "setups_detected": [
      "Breakout+Retest",
      "Rejet S/R",
      "Pullback Tendance",
      "Range Propre"
    ],
    "proposed_entry": 4672.0,
    "sl": 4642.0,
    "tp1": 4702.0,
    "tp2": 4747.0,
    "rr_tp2": 2.5,
    "rr_min": 2.0,
    "score_rules": 100,
    "reasons_rules": [
      "Bias H1 aligné",
      "Setup clair",
      "RR TP2 >= 2.0",
      "Spread OK",
      "Volatilité OK",
      "News OK"
    ],
    "state": {
      "daily_budget_used": 100.0,
      "cooldown_ok": true,
      "last_signal_key": null,
      "consecutive_losses": 0
    },
    "timestamps": {
      "ts_utc": "2026-01-21T09:00:00+00:00",
      "ts_paris": "2026-01-21T10:00:00+01:00"
    },
    "data_latency_ms": 15
  },
  "ai_output": null,
  "ai_enabled": false,
  "data_latency_ms": 15,
  "ai_latency_ms": null,
  "signal_key": "400f639cb5505a9ce916b522297df15873a09753"
}
```
DB (dernieres lignes):
```json
[
  {
    "status": "NO_GO",
    "blocked_by": "DAILY_BUDGET_REACHED",
    "score_total": 100,
    "score_effective": 0,
    "decision_packet_json": "{\"session_ok\": true, \"news_lock\": false, \"news_next_event\": {\"datetime_iso\": \"2026-01-21T16:00:00+01:00\", \"impact\": \"HIGH\", \"title\": \"FOMC Minutes\"}, \"spread\": 12.0, \"spread_max\": 20.0, \"atr\": 1.1, \"atr_max\": 2.0, \"bias_h1\": \"UP\", \"setups_detected\": [\"Breakout+Retest\", \"Rejet S/R\", \"Pullback Tendance\", \"Range Propre\"], \"proposed_entry\": 4672.0, \"sl\": 4642.0, \"tp1\": 4702.0, \"tp2\": 4747.0, \"rr_tp2\": 2.5, \"rr_min\": 2.0, \"score_rules\": 100, \"reasons_rules\": [\"Bias H1 align\\u00e9\", \"Setup clair\", \"RR TP2 >= 2.0\", \"Spread OK\", \"Volatilit\\u00e9 OK\", \"News OK\"], \"state\": {\"daily_budget_used\": 100.0, \"cooldown_ok\": true, \"last_signal_key\": null, \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-21T09:00:00+00:00\", \"ts_paris\": \"2026-01-21T10:00:00+01:00\"}, \"data_latency_ms\": 15}"
  }
]
```

### DATA_OFF
Réponse:
```json
{
  "decision": {
    "status": "NO_GO",
    "blocked_by": "DATA_OFF",
    "score_total": 35,
    "score_effective": 0,
    "confidence": 50,
    "quality": "B",
    "why": [
      "Données marché indisponibles"
    ]
  },
  "message": "NO GO ❌ XAUUSD (M15)\nBloqué par : DATA_OFF — Données marché indisponibles\nScore marché : 35/100",
  "decision_packet": {
    "session_ok": true,
    "news_lock": false,
    "news_next_event": null,
    "spread": 21.0,
    "spread_max": 20.0,
    "atr": 3.0,
    "atr_max": 2.0,
    "bias_h1": "RANGE",
    "setups_detected": [],
    "proposed_entry": 0.0,
    "sl": 0.0,
    "tp1": 0.0,
    "tp2": 0.0,
    "rr_tp2": 0.0,
    "rr_min": 2.0,
    "score_rules": 35,
    "reasons_rules": [
      "Données marché indisponibles"
    ],
    "state": {
      "daily_budget_used": 0.0,
      "cooldown_ok": true,
      "last_signal_key": null,
      "consecutive_losses": 0
    },
    "timestamps": {
      "ts_utc": "2026-01-22T08:16:18.222833+00:00",
      "ts_paris": "2026-01-22T09:16:18.222833+01:00"
    },
    "data_latency_ms": 9999
  },
  "ai_output": null,
  "ai_enabled": false,
  "data_latency_ms": 9999,
  "ai_latency_ms": null,
  "signal_key": "cacf27d864fb98593184f238a4aade34bff0ed66"
}
```
DB (dernieres lignes):
```json
[
  {
    "status": "NO_GO",
    "blocked_by": "DATA_OFF",
    "score_total": 35,
    "score_effective": 0,
    "decision_packet_json": "{\"session_ok\": true, \"news_lock\": false, \"news_next_event\": null, \"spread\": 21.0, \"spread_max\": 20.0, \"atr\": 3.0, \"atr_max\": 2.0, \"bias_h1\": \"RANGE\", \"setups_detected\": [], \"proposed_entry\": 0.0, \"sl\": 0.0, \"tp1\": 0.0, \"tp2\": 0.0, \"rr_tp2\": 0.0, \"rr_min\": 2.0, \"score_rules\": 35, \"reasons_rules\": [\"Donn\\u00e9es march\\u00e9 indisponibles\"], \"state\": {\"daily_budget_used\": 0.0, \"cooldown_ok\": true, \"last_signal_key\": null, \"consecutive_losses\": 0}, \"timestamps\": {\"ts_utc\": \"2026-01-22T08:16:18.222833+00:00\", \"ts_paris\": \"2026-01-22T09:16:18.222833+01:00\"}, \"data_latency_ms\": 9999}"
  }
]
```

## Performance /analyze (10 appels)
- min: 0.0109s
- avg: 0.0129s
- max: 0.0161s
