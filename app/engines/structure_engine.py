"""
Moteur de structure marché — style trader pro.
Détecte: swing points, S/R, breakout, pullback, structure HH/HL.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class SwingPoint:
    idx: int
    typ: str  # "high" | "low"
    price: float


@dataclass(frozen=True)
class StructureResult:
    swings: List[SwingPoint]
    sr_levels: List[float]
    structure: str  # "BULLISH" | "BEARISH" | "RANGE"
    last_swing_high: Optional[float]
    last_swing_low: Optional[float]
    breakout_level: Optional[float]
    pullback_to_level: Optional[float]


@dataclass(frozen=True)
class StrongTrendResult:
    """Résultat détection tendance forte M15 pour EXTENSION_MOVE adaptatif."""
    trend_direction: str  # "BUY" | "SELL" | "NONE"
    last_trend_pivot_price: Optional[float]  # dernier HL (BUY) ou dernier LH (SELL)


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


def detect_swings(candles: List[dict], lookback: int = 2) -> List[SwingPoint]:
    """
    Détection fractale: un high est un swing high si plus haut que lookback barres
    à gauche et à droite. Idem pour les lows.
    """
    highs = _extract_series(candles, "high")
    lows = _extract_series(candles, "low")
    swings: List[SwingPoint] = []
    n = len(highs)
    if n < 2 * lookback + 1:
        return swings
    for i in range(lookback, n - lookback):
        h = highs[i]
        is_swing_high = all(highs[j] <= h for j in range(i - lookback, i + lookback + 1) if j != i)
        if is_swing_high:
            swings.append(SwingPoint(idx=i, typ="high", price=h))
        l = lows[i]
        is_swing_low = all(lows[j] >= l for j in range(i - lookback, i + lookback + 1) if j != i)
        if is_swing_low:
            swings.append(SwingPoint(idx=i, typ="low", price=l))
    return swings


def cluster_levels(prices: List[float], tolerance_pct: float = 0.002) -> List[float]:
    """Regroupe les prix proches en niveaux S/R."""
    if not prices:
        return []
    sorted_prices = sorted(set(prices), reverse=True)
    levels: List[float] = []
    for p in sorted_prices:
        if not levels:
            levels.append(p)
            continue
        last = levels[-1]
        if abs(p - last) / last <= tolerance_pct:
            levels[-1] = (levels[-1] + p) / 2
        else:
            levels.append(p)
    return levels


def detect_sr_levels(swings: List[SwingPoint], min_touches: int = 2) -> List[float]:
    """S/R = niveaux avec plusieurs touches (swing points proches)."""
    if not swings:
        return []
    prices = [s.price for s in swings]
    return cluster_levels(prices, tolerance_pct=0.003)


def detect_market_structure(swings: List[SwingPoint]) -> str:
    """
    Structure HH/HL = haussier, LH/LL = baissier.
    Compare les derniers swing highs et lows.
    """
    highs = [s for s in swings if s.typ == "high"]
    lows = [s for s in swings if s.typ == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "RANGE"
    highs_sorted = sorted(highs, key=lambda x: x.idx)
    lows_sorted = sorted(lows, key=lambda x: x.idx)
    h1, h2 = highs_sorted[-2], highs_sorted[-1]
    l1, l2 = lows_sorted[-2], lows_sorted[-1]
    hh = h2.price > h1.price
    hl = l2.price > l1.price
    lh = h2.price < h1.price
    ll = l2.price < l1.price
    if hh and hl:
        return "BULLISH"
    if lh and ll:
        return "BEARISH"
    return "RANGE"


def analyze_structure(candles: List[dict]) -> StructureResult:
    """Analyse complète: swings, S/R, structure, breakout/pullback potentiels."""
    if not candles:
        return StructureResult(
            swings=[],
            sr_levels=[],
            structure="RANGE",
            last_swing_high=None,
            last_swing_low=None,
            breakout_level=None,
            pullback_to_level=None,
        )
    swings = detect_swings(candles, lookback=2)
    sr_levels = detect_sr_levels(swings)
    structure = detect_market_structure(swings)
    highs = [s for s in swings if s.typ == "high"]
    lows = [s for s in swings if s.typ == "low"]
    last_sh = highs[-1].price if highs else None
    last_sl = lows[-1].price if lows else None
    closes = _extract_series(candles, "close")
    last_close = closes[-1] if closes else None
    breakout_level: Optional[float] = None
    pullback_to_level: Optional[float] = None
    zone_tolerance_pct = 0.0015
    for level in sr_levels[-6:]:
        if last_close is None:
            break
        dist = abs(last_close - level) / level if level else 0
        if dist <= zone_tolerance_pct:
            pullback_to_level = level
            break
    return StructureResult(
        swings=swings,
        sr_levels=sr_levels[-10:],
        structure=structure,
        last_swing_high=last_sh,
        last_swing_low=last_sl,
        breakout_level=breakout_level,
        pullback_to_level=pullback_to_level,
    )


def _momentum_m15_aligned(closes: List[float], direction: str, n: int = 5) -> bool:
    """Momentum M15 aligné: récents > anciens (BUY) ou récents < anciens (SELL)."""
    if len(closes) < n * 2:
        return False
    recent = sum(closes[-n:]) / n
    older = sum(closes[-2 * n : -n]) / n
    if direction == "BUY":
        return recent > older
    return recent < older


def detect_strong_trend_m15(bars_m15: List[dict]) -> StrongTrendResult:
    """
    Détection tendance forte M15 pour EXTENSION_MOVE adaptatif.
    BUY: 2 Higher High consécutifs + 2 Higher Low consécutifs + momentum M15 aligné.
    SELL: 2 Lower Low + 2 Lower High + momentum aligné.
    Retourne last_trend_pivot_price = dernier HL (BUY) ou dernier LH (SELL).
    """
    if not bars_m15 or len(bars_m15) < 10:
        return StrongTrendResult(trend_direction="NONE", last_trend_pivot_price=None)
    swings = detect_swings(bars_m15, lookback=2)
    highs = sorted([s for s in swings if s.typ == "high"], key=lambda x: x.idx)
    lows = sorted([s for s in swings if s.typ == "low"], key=lambda x: x.idx)
    closes = _extract_series(bars_m15, "close")
    if len(highs) < 3 or len(lows) < 3 or len(closes) < 10:
        return StrongTrendResult(trend_direction="NONE", last_trend_pivot_price=None)
    h1, h2, h3 = highs[-3], highs[-2], highs[-1]
    l1, l2, l3 = lows[-3], lows[-2], lows[-1]
    two_hh = h2.price > h1.price and h3.price > h2.price
    two_hl = l2.price > l1.price and l3.price > l2.price
    two_ll = l2.price < l1.price and l3.price < l2.price
    two_lh = h2.price < h1.price and h3.price < h2.price
    if two_hh and two_hl and _momentum_m15_aligned(closes, "BUY"):
        return StrongTrendResult(trend_direction="BUY", last_trend_pivot_price=l3.price)
    if two_ll and two_lh and _momentum_m15_aligned(closes, "SELL"):
        return StrongTrendResult(trend_direction="SELL", last_trend_pivot_price=h3.price)
    return StrongTrendResult(trend_direction="NONE", last_trend_pivot_price=None)
