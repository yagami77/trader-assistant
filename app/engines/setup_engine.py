from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SetupResult:
    setups: List[str]
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr_tp2: float


def detect_setups(candles: List[dict]) -> SetupResult:
    if not candles:
        return SetupResult(setups=[], entry=0.0, sl=0.0, tp1=0.0, tp2=0.0, rr_tp2=0.0)

    last = candles[-1]
    close = float(last.get("close", 4660.0))
    entry = close
    sl = close - 30.0
    tp1 = close + 30.0
    tp2 = close + 75.0
    rr_tp2 = (tp2 - entry) / max(0.0001, (entry - sl))
    setups = ["Breakout+Retest", "Rejet S/R", "Pullback Tendance", "Range Propre"]
    return SetupResult(setups=setups, entry=entry, sl=sl, tp1=tp1, tp2=tp2, rr_tp2=rr_tp2)
