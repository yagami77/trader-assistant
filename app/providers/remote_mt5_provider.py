from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import get_settings


class RemoteMT5Provider:
    def _request(self, path: str, params: Dict[str, str]) -> Dict:
        settings = get_settings()
        if not settings.mt5_bridge_url:
            raise RuntimeError("MT5_BRIDGE_URL manquant")
        url = settings.mt5_bridge_url.rstrip("/") + path
        last_exc: Exception | None = None
        for _ in range(2):
            try:
                resp = httpx.get(url, params=params, timeout=4.0)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        raise RuntimeError(f"MT5 bridge error: {last_exc}")

    def _request_with_fallback(self, path: str, primary: Dict[str, str], fallback: Dict[str, str]) -> Dict:
        try:
            return self._request(path, primary)
        except Exception:
            return self._request(path, fallback)

    def get_candles(self, symbol: str, timeframe: str, n: int) -> List[Dict[str, float]]:
        payload = self._request_with_fallback(
            "/candles",
            {"symbol": symbol, "timeframe": timeframe, "count": str(n)},
            {"symbol": symbol, "tf": timeframe, "n": str(n)},
        )
        return payload.get("candles", [])

    def get_spread(self, symbol: str) -> float:
        payload = self._request("/spread", {"symbol": symbol})
        return float(payload.get("spread_points", 0.0))

    def get_symbol_specs(self, symbol: str) -> Dict[str, float]:
        return {
            "tick_value": 1.0,
            "tick_size": 0.01,
            "lot_min": 0.01,
            "lot_step": 0.01,
        }

    def get_server_time(self) -> datetime:
        payload = self._request("/tick", {"symbol": "XAUUSD"})
        ts = payload.get("ts")
        if ts:
            return datetime.fromisoformat(ts)
        return datetime.now(timezone.utc)

    def get_tick(self, symbol: str) -> Optional[Tuple[float, float]]:
        try:
            payload = self._request("/tick", {"symbol": symbol})
            bid = payload.get("bid")
            ask = payload.get("ask")
            if bid is not None and ask is not None:
                return (float(bid), float(ask))
        except Exception:
            pass
        return None
