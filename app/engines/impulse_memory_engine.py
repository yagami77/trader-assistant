"""
Mémoire d'impulsion M15 — détecte les grosses bougies (impulsions) sur un historique long.
Utilisé pour EXTENSION_MOVE : reference_level = impulse_anchor si dispo, sinon breakout/structure.
Permet de laisser passer les retests/pullbacks proches de l'ancre malgré extension.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional


@dataclass(frozen=True)
class ImpulseMemory:
    last_impulse_dir: str  # "BUY" | "SELL"
    last_impulse_ts_utc: Optional[str]
    impulse_range_pts: float
    impulse_anchor_price: float
    key_levels: List[float]


def _compute_atr(candles: List[dict], period: int = 14) -> float:
    """ATR(14) sur les bougies."""
    highs = _extract_series(candles, "high")
    lows = _extract_series(candles, "low")
    closes = _extract_series(candles, "close")
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return (max(highs[-5:]) - min(lows[-5:])) / 5 if len(highs) >= 5 else 20.0
    tr_list: list = []
    for i in range(1, min(len(highs), len(lows), len(closes))):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)
    if len(tr_list) < period:
        return tr_list[-1] if tr_list else 20.0
    return sum(tr_list[-period:]) / period


def _extract_series(candles: List[dict], key: str) -> List[float]:
    out: List[float] = []
    for c in candles:
        v = c.get(key)
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _parse_bar_ts(candle: dict) -> Optional[str]:
    v = candle.get("ts") or candle.get("time_msc") or candle.get("time")
    if v is None:
        return None
    if isinstance(v, (int, float)):
        ts = float(v)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if isinstance(v, str):
        return v.strip() or None
    return None


def compute_impulse_memory(
    candles_m15: List[dict],
    impulse_atr_mult: float = 1.8,
) -> Optional[ImpulseMemory]:
    """
    Détecte la dernière bougie d'impulsion M15 (range >= ATR * mult).
    Retourne None si aucune impulsion trouvée.
    """
    if not candles_m15 or len(candles_m15) < 15:
        return None

    atr = _compute_atr(candles_m15)
    threshold = atr * impulse_atr_mult

    # Parcourir de la plus récente vers la plus ancienne
    for i in range(len(candles_m15) - 1, -1, -1):
        c = candles_m15[i]
        high = c.get("high")
        low = c.get("low")
        open_ = c.get("open")
        close = c.get("close")
        if high is None or low is None:
            continue
        try:
            h, l_ = float(high), float(low)
        except (TypeError, ValueError):
            continue
        range_pts = h - l_
        if range_pts < threshold:
            continue

        # Bougie d'impulsion trouvée — direction = sens du mouvement (bullish → BUY, bearish → SELL)
        o = float(open_) if open_ is not None else l_
        cl = float(close) if close is not None else h
        direction = "BUY" if cl >= o else "SELL"
        anchor = l_ if direction == "BUY" else h  # niveau d'origine du move
        ts_utc = _parse_bar_ts(c)

        # Key levels: anchor + niveau opposé de la bougie
        key_levels = [anchor, h if direction == "BUY" else l_]

        return ImpulseMemory(
            last_impulse_dir=direction,
            last_impulse_ts_utc=ts_utc,
            impulse_range_pts=round(range_pts, 1),
            impulse_anchor_price=anchor,
            key_levels=key_levels,
        )

    return None
