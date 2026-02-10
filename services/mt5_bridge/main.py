"""
Bridge MT5 — connexion à MetaTrader 5 pour données réelles (prix, bougies).
Remplace l'ancien stub. Expose /health, /tick, /spread, /candles sur le port 8080.
MT5 doit être installé et ouvert (terminal lancé) pour que le bridge fonctionne.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None

app = FastAPI(title="MT5 Bridge", version="2.0")

TF_MAP: Dict[str, int] = {}
if MT5_AVAILABLE:
    TF_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }


def _ensure_mt5_initialized() -> None:
    if not MT5_AVAILABLE:
        raise HTTPException(status_code=503, detail="MetaTrader5 package not installed")
    if mt5.terminal_info() is not None:
        return
    ok = mt5.initialize()
    if not ok:
        err = mt5.last_error()
        raise HTTPException(status_code=503, detail=f"MT5 initialize failed: {err}")


def _ensure_symbol(symbol: str) -> None:
    if not mt5.symbol_select(symbol, True):
        raise HTTPException(status_code=400, detail=f"Symbol not available: {symbol}")


def _time_msc_to_iso(time_msc: int) -> str:
    return datetime.fromtimestamp(time_msc / 1000.0, tz=timezone.utc).isoformat()


@app.on_event("startup")
def on_startup() -> None:
    if MT5_AVAILABLE:
        try:
            _ensure_mt5_initialized()
        except Exception:
            pass


@app.on_event("shutdown")
def on_shutdown() -> None:
    if MT5_AVAILABLE:
        try:
            mt5.shutdown()
        except Exception:
            pass


@app.get("/health")
def health() -> Dict[str, Any]:
    if not MT5_AVAILABLE:
        raise HTTPException(status_code=503, detail="MetaTrader5 package not installed")
    try:
        _ensure_mt5_initialized()
        info = mt5.terminal_info()
        if info is None:
            raise HTTPException(status_code=503, detail="MT5 terminal_info unavailable")
        return {"status": "ok", "terminal": "MetaTrader 5", "ts_utc": datetime.now(timezone.utc).isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/tick")
def tick(symbol: str) -> Dict[str, Any]:
    _ensure_mt5_initialized()
    _ensure_symbol(symbol)

    t = mt5.symbol_info_tick(symbol)
    if t is None:
        raise HTTPException(status_code=503, detail="No tick data")

    ts_iso = _time_msc_to_iso(int(t.time_msc))
    return {
        "symbol": symbol,
        "bid": float(t.bid),
        "ask": float(t.ask),
        "time_msc": int(t.time_msc),
        "ts": ts_iso,
    }


@app.get("/spread")
def spread(symbol: str) -> Dict[str, Any]:
    _ensure_mt5_initialized()
    _ensure_symbol(symbol)

    t = mt5.symbol_info_tick(symbol)
    if t is None:
        raise HTTPException(status_code=503, detail="No tick data")

    spread_price = float(t.ask) - float(t.bid)
    info = mt5.symbol_info(symbol)
    point = float(info.point) if info and info.point else 0.01
    spread_points = (spread_price / point) if point else spread_price * 100

    return {
        "symbol": symbol,
        "bid": float(t.bid),
        "ask": float(t.ask),
        "spread_price": float(spread_price),
        "spread_points": float(spread_points),
        "time_msc": int(t.time_msc),
    }


@app.get("/candles")
def candles(
    symbol: str,
    timeframe: Optional[str] = None,
    count: int = 200,
    tf: Optional[str] = None,
    n: Optional[int] = None,
) -> Dict[str, Any]:
    if timeframe is None:
        timeframe = tf
    if n is not None:
        count = n

    if not timeframe:
        raise HTTPException(status_code=422, detail="timeframe is required (timeframe or tf)")

    tf_const = TF_MAP.get(timeframe.upper())
    if tf_const is None:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {timeframe}")

    if count <= 0:
        raise HTTPException(status_code=400, detail="count must be > 0")
    if count > 5000:
        count = 5000

    _ensure_mt5_initialized()
    _ensure_symbol(symbol)

    rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, count)
    if rates is None:
        raise HTTPException(status_code=503, detail=f"copy_rates failed: {mt5.last_error()}")
    if len(rates) == 0:
        raise HTTPException(status_code=503, detail="No candles returned")

    out: List[Dict[str, Any]] = []
    for r in rates:
        out.append({
            "time": int(r["time"]),
            "time_msc": int(r["time"]) * 1000,
            "ts": datetime.fromtimestamp(int(r["time"]), tz=timezone.utc).isoformat(),
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "tick_volume": int(r["tick_volume"]),
            "spread": int(r["spread"]),
            "real_volume": int(r["real_volume"]),
        })

    return {
        "symbol": symbol,
        "timeframe": timeframe.upper(),
        "n": len(out),
        "candles": out,
    }
