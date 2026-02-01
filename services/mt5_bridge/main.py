from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="MT5 Bridge", version="0.1.0")

SUPPORTED_TF = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/candles")
def candles(symbol: str, tf: str = Query(...), n: int = Query(..., ge=1, le=2000)) -> dict:
    if tf not in SUPPORTED_TF:
        raise HTTPException(status_code=400, detail="TF invalide")
    if symbol.upper() != "XAUUSD":
        raise HTTPException(status_code=404, detail="Symbol introuvable")
    now = datetime.now(timezone.utc)
    data: List[dict] = []
    for _ in range(n):
        data.append(
            {
                "ts": now.isoformat(),
                "open": 4660.0,
                "high": 4685.0,
                "low": 4645.0,
                "close": 4672.0,
                "volume": 1200.0,
            }
        )
    return {"candles": data}


@app.get("/tick")
def tick(symbol: str) -> dict:
    if symbol.upper() != "XAUUSD":
        raise HTTPException(status_code=404, detail="Symbol introuvable")
    now = datetime.now(timezone.utc)
    return {"bid": 4671.5, "ask": 4672.0, "ts": now.isoformat()}


@app.get("/spread")
def spread(symbol: str) -> dict:
    if symbol.upper() != "XAUUSD":
        raise HTTPException(status_code=404, detail="Symbol introuvable")
    now = datetime.now(timezone.utc)
    return {
        "spread_points": 12.0,
        "bid": 4671.5,
        "ask": 4672.0,
        "ts": now.isoformat(),
    }
