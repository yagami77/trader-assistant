import os
from datetime import datetime, timezone
from typing import Dict, List


class MockDataProvider:
    def _maybe_fail(self) -> None:
        if os.environ.get("MOCK_PROVIDER_FAIL", "").lower() == "true":
            raise RuntimeError("Mock provider failure")

    def get_candles(self, symbol: str, timeframe: str, n: int) -> List[Dict[str, float]]:
        self._maybe_fail()
        now = self.get_server_time()
        return [
            {
                "ts": now.isoformat(),
                "open": 4660.0,
                "high": 4685.0,
                "low": 4645.0,
                "close": 4672.0,
                "volume": 1200.0,
            }
            for _ in range(n)
        ]

    def get_spread(self, symbol: str) -> float:
        self._maybe_fail()
        return 12.0

    def get_symbol_specs(self, symbol: str) -> Dict[str, float]:
        self._maybe_fail()
        return {
            "tick_value": 1.0,
            "tick_size": 0.01,
            "lot_min": 0.01,
            "lot_step": 0.01,
        }

    def get_server_time(self) -> datetime:
        self._maybe_fail()
        forced = os.environ.get("MOCK_SERVER_TIME_UTC")
        if forced:
            return datetime.fromisoformat(forced)
        return datetime.now(timezone.utc)

    def get_tick(self, symbol: str):
        self._maybe_fail()
        return (4671.5, 4672.0)  # bid, ask
