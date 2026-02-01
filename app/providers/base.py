from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Protocol


class DataProvider(Protocol):
    def get_candles(self, symbol: str, timeframe: str, n: int) -> List[Dict[str, float]]:
        ...

    def get_spread(self, symbol: str) -> float:
        ...

    def get_symbol_specs(self, symbol: str) -> Dict[str, float]:
        ...

    def get_server_time(self) -> datetime:
        ...
