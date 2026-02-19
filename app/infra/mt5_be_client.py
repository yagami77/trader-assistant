"""
Client pour modifier le SL d'une position MT5 via le bridge (break-even automatique).
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)


def mt5_modify_sl_to_be(symbol: str, new_sl: float, direction: str) -> bool:
    """
    Modifie le SL de la position ouverte sur MT5 via le bridge.
    Retourne True si succès, False sinon (log l'erreur détaillée).
    Utilise MT5_POSITION_SYMBOL si défini (broker avec symbole différent: XAUUSDm, GOLD, etc.).
    """
    settings = get_settings()
    bridge_url = (settings.mt5_bridge_url or "").strip()
    if not bridge_url:
        log.debug("MT5_BRIDGE_URL vide, skip modification SL sur MT5")
        return False

    sym = (getattr(settings, "mt5_position_symbol", "") or "").strip() or symbol
    url = bridge_url.rstrip("/") + "/position/modify-sl"
    payload = {
        "symbol": sym,
        "new_sl": new_sl,
        "direction": direction.upper(),
    }
    try:
        resp = httpx.post(url, json=payload, timeout=5.0)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if data.get("ok"):
            log.info("MT5 SL modifié à BE: %s %s new_sl=%.2f", sym, direction, new_sl)
            return True
        err = data.get("error", f"HTTP {resp.status_code}")
        retcode = data.get("retcode")
        log.warning("MT5 modify SL failed: %s (retcode=%s, symbol=%s)", err, retcode, sym)
        return False
    except Exception as e:  # noqa: BLE001
        log.warning("MT5 modify SL error: %s (symbol=%s)", e, sym)
        return False


def mt5_close_partial_at_tp1(symbol: str, direction: str, percent: float = 50.0) -> bool:
    """
    Clôture X% de la position au TP1. Retourne True si succès.
    """
    settings = get_settings()
    bridge_url = (settings.mt5_bridge_url or "").strip()
    if not bridge_url:
        log.debug("MT5_BRIDGE_URL vide, skip clôture partielle")
        return False

    url = bridge_url.rstrip("/") + "/position/close-partial"
    payload = {
        "symbol": symbol,
        "direction": direction.upper(),
        "percent": percent,
    }
    try:
        resp = httpx.post(url, json=payload, timeout=5.0)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if data.get("ok"):
            vol = data.get("volume_closed", 0)
            log.info("MT5 clôture partielle %s%% OK: %s %s vol=%.2f", percent, symbol, direction, vol)
            return True
        err = data.get("error", f"HTTP {resp.status_code}")
        log.warning("MT5 close partial failed: %s", err)
        return False
    except Exception as e:  # noqa: BLE001
        log.warning("MT5 close partial error: %s", e)
        return False
