"""
Bridge MT5 — connexion à MetaTrader 5 pour données réelles (prix, bougies).
Remplace l'ancien stub. Expose /health, /tick, /spread, /candles sur le port 8080.
MT5 doit être installé et ouvert (terminal lancé) pour que le bridge fonctionne.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_HEALTH_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="health")

from pydantic import BaseModel
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
    """Vérifie que MT5 est connecté (initialize fait au startup)."""
    if not MT5_AVAILABLE:
        raise HTTPException(status_code=503, detail="MetaTrader5 package not installed")
    if mt5.terminal_info() is None:
        raise HTTPException(
            status_code=503,
            detail="MT5 non connecté — ouvrir le terminal MetaTrader 5 sur le VPS",
        )


def _ensure_symbol(symbol: str) -> None:
    if not mt5.symbol_select(symbol, True):
        raise HTTPException(status_code=400, detail=f"Symbol not available: {symbol}")


def _time_msc_to_iso(time_msc: int) -> str:
    return datetime.fromtimestamp(time_msc / 1000.0, tz=timezone.utc).isoformat()


def _init_mt5_background() -> None:
    """En Session 0 / NSSM, la lib doit appeler initialize() pour voir le terminal."""
    if not MT5_AVAILABLE:
        return
    for _ in range(60):  # ~2 min
        if mt5.terminal_info() is not None:
            return
        mt5.initialize()
        time.sleep(2)


@app.on_event("startup")
def on_startup() -> None:
    # Ne pas appeler mt5.initialize() ici : la lib peut bloquer tout le processus (GIL).
    # La connexion MT5 se fait au premier appel (ex. /health avec timeout 5s).
    pass


@app.on_event("shutdown")
def on_shutdown() -> None:
    if MT5_AVAILABLE:
        try:
            mt5.shutdown()
        except Exception:
            pass


@app.get("/ping")
def ping() -> Dict[str, Any]:
    """Répond immédiatement sans appeler MT5 (vérifier que le bridge écoute)."""
    return {"status": "pong", "ts_utc": datetime.now(timezone.utc).isoformat()}


def _health_check_mt5() -> Any:
    """Initialize si besoin puis retourne terminal_info(). Appeler dans l'executor (timeout)."""
    if mt5.terminal_info() is None:
        mt5.initialize()
    return mt5.terminal_info()


@app.get("/health")
def health() -> Dict[str, Any]:
    """Vérifie MT5 connecté. Timeout 8s (initialize + terminal_info)."""
    if not MT5_AVAILABLE:
        raise HTTPException(status_code=503, detail="MetaTrader5 package not installed")
    try:
        fut = _HEALTH_EXECUTOR.submit(_health_check_mt5)
        info = fut.result(timeout=20.0)
    except FuturesTimeoutError:
        raise HTTPException(
            status_code=503,
            detail="MT5 timeout (20s) — bridge et MT5 en Session 0 ?",
        )
    if info is None:
        raise HTTPException(
            status_code=503,
            detail="MT5 non connecté — ouvrir le terminal MetaTrader 5 sur le VPS",
        )
    return {"status": "ok", "terminal": "MetaTrader 5", "ts_utc": datetime.now(timezone.utc).isoformat()}


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


@app.get("/positions")
def positions(symbol: Optional[str] = None) -> Dict[str, Any]:
    """Liste les positions ouvertes. Si symbol fourni, filtre par symbole."""
    _ensure_mt5_initialized()
    positions_list = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
    if positions_list is None:
        return {"positions": [], "error": mt5.last_error()}
    out = []
    for p in positions_list:
        out.append({
            "ticket": int(p.ticket),
            "symbol": str(p.symbol),
            "type": "BUY" if p.type == 0 else "SELL",
            "volume": float(p.volume),
            "price_open": float(p.price_open),
            "sl": float(p.sl) if p.sl else None,
            "tp": float(p.tp) if p.tp else None,
            "price_current": float(p.price_current),
            "profit": float(p.profit),
        })
    return {"positions": out}


class ModifySLRequest(BaseModel):
    symbol: str
    new_sl: float
    ticket: Optional[int] = None
    direction: Optional[str] = None


def _find_position(symbol: str, direction: str, ticket: Optional[int] = None) -> tuple:
    """
    Trouve une position par symbole (exact ou partiel XAUUSD/XAUUSDm/GOLD) et direction.
    Retourne (position, error) ou (None, error_msg).
    """
    want_type = 0 if (direction or "").upper() == "BUY" else 1
    sym_upper = symbol.upper()

    def _match(p) -> bool:
        if ticket is not None:
            return p.ticket == ticket
        return p.type == want_type

    # 1) Essai direct par symbole
    positions_list = mt5.positions_get(symbol=symbol)
    if positions_list is None:
        return None, "positions_get failed"
    for p in positions_list:
        if _match(p):
            return p, None

    # 2) Si vide : toutes positions, match partiel (XAUUSD vs XAUUSDm, GOLD, etc.)
    positions_list = mt5.positions_get()
    if positions_list is None or len(positions_list) == 0:
        return None, f"No position found for {symbol} {direction}"
    for p in positions_list:
        p_sym = str(p.symbol).upper()
        ok = p_sym == sym_upper or sym_upper in p_sym or p_sym.startswith("XAUUSD") or p_sym == "GOLD"
        if ok and _match(p):
            return p, None
    return None, f"No {direction} position for {symbol} (tried exact + XAUUSD/GOLD)"


@app.post("/position/modify-sl")
def position_modify_sl(body: ModifySLRequest) -> Dict[str, Any]:
    """
    Modifie le SL d'une position ouverte.
    - symbol: symbole (ex. XAUUSD, GOLD, XAUUSDm selon broker)
    - new_sl: nouveau prix du stop loss
    - ticket: numéro de ticket (optionnel)
    - direction: BUY ou SELL (requis si ticket absent)
    """
    symbol = body.symbol
    new_sl = body.new_sl
    ticket = body.ticket
    direction = body.direction
    _ensure_mt5_initialized()

    pos, err = _find_position(symbol, direction or "", ticket)
    if pos is None:
        return {"ok": False, "error": err or "No position found", "retcode": None}

    _ensure_symbol(str(pos.symbol))

    # TRADE_ACTION_SLTP : utiliser le symbole EXACT de la position (broker-specific)
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": str(pos.symbol),
        "position": pos.ticket,
        "sl": new_sl,
        "tp": pos.tp if pos.tp else 0.0,
    }
    result = mt5.order_send(request)
    if result is None:
        err = mt5.last_error()
        return {"ok": False, "error": str(err) if err else "order_send failed", "retcode": None}

    retcode = getattr(result, "retcode", None)
    if retcode != mt5.TRADE_RETCODE_DONE:
        return {
            "ok": False,
            "error": getattr(result, "comment", str(retcode)),
            "retcode": retcode,
        }
    return {"ok": True, "ticket": pos.ticket, "new_sl": new_sl, "retcode": retcode}


class ClosePartialRequest(BaseModel):
    symbol: str
    direction: str  # BUY ou SELL (type de la position ouverte)
    percent: float = 50.0  # % du volume à clôturer


@app.post("/position/close-partial")
def position_close_partial(body: ClosePartialRequest) -> Dict[str, Any]:
    """
    Clôture partiellement une position (ex. 50% au TP1).
    - symbol: XAUUSD
    - direction: BUY ou SELL (type de la position à réduire)
    - percent: 50 = fermer 50% du volume
    """
    _ensure_mt5_initialized()
    _ensure_symbol(body.symbol)

    positions_list = mt5.positions_get(symbol=body.symbol)
    if positions_list is None or len(positions_list) == 0:
        return {"ok": False, "error": "No position found", "volume_closed": 0}

    want_type = 0 if body.direction.upper() == "BUY" else 1
    pos = None
    for p in positions_list:
        if p.type == want_type:
            pos = p
            break
    if pos is None:
        return {"ok": False, "error": f"No {body.direction} position for {body.symbol}", "volume_closed": 0}

    percent = max(0.01, min(99.99, float(body.percent)))
    vol_total = float(pos.volume)
    vol_close = round(vol_total * percent / 100.0, 2)
    if vol_close <= 0:
        return {"ok": False, "error": "Volume to close too small", "volume_closed": 0}

    # Prix marché : BUY → on vend au bid ; SELL → on achète à l'ask
    tick = mt5.symbol_info_tick(body.symbol)
    if tick is None:
        return {"ok": False, "error": "No tick", "volume_closed": 0}
    price = float(tick.bid) if body.direction.upper() == "BUY" else float(tick.ask)
    close_type = mt5.ORDER_TYPE_SELL if body.direction.upper() == "BUY" else mt5.ORDER_TYPE_BUY

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": body.symbol,
        "volume": vol_close,
        "type": close_type,
        "position": pos.ticket,
        "price": price,
        "deviation": 20,
    }
    result = mt5.order_send(request)
    if result is None:
        err = mt5.last_error()
        return {"ok": False, "error": str(err) if err else "order_send failed", "volume_closed": 0}

    retcode = getattr(result, "retcode", None)
    if retcode != mt5.TRADE_RETCODE_DONE:
        return {
            "ok": False,
            "error": getattr(result, "comment", str(retcode)),
            "retcode": retcode,
            "volume_closed": 0,
        }
    return {"ok": True, "volume_closed": vol_close, "retcode": retcode}
