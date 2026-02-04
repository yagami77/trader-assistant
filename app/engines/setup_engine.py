from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.models import Bias


@dataclass(frozen=True)
class SetupResult:
    setups: List[str]
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr_tp2: float
    direction: str
    bias: Bias
    atr: float  # ATR exprimé en unités de prix


def detect_setups(
    candles: List[dict],
    tick_size: float = 0.0,
    sl_max_atr_multiple: float = 1.5,
    sl_max_points: float | None = None,
) -> SetupResult:
    if not candles:
        return SetupResult(
            setups=[],
            entry=0.0,
            sl=0.0,
            tp1=0.0,
            tp2=0.0,
            rr_tp2=0.0,
            direction="BUY",
            bias=Bias.range,
            atr=0.0,
        )

    closes = _extract_series(candles, "close")
    highs = _extract_series(candles, "high")
    lows = _extract_series(candles, "low")
    entry = closes[-1]
    atr_price = _compute_atr(candles)
    avg_range = _average_range(highs, lows)
    tick = tick_size if tick_size > 0 else 0.01
    bias = _infer_bias(closes, atr_price)
    direction = _infer_direction(bias, closes)
    setups = _build_setups(direction, bias)

    max_risk_atr = atr_price * sl_max_atr_multiple if atr_price > 0 else tick * 20
    if sl_max_points and sl_max_points > 0:
        max_risk = min(max_risk_atr, sl_max_points)
    else:
        max_risk = max_risk_atr
    max_risk = max(max_risk, tick * 5)
    min_risk = max(atr_price * 0.25, tick * 5)
    sl_buffer = max(atr_price * 0.2, tick * 5)
    tp_buffer = max(atr_price * 0.05, tick * 2)

    swing_low = min(lows[-5:]) if len(lows) >= 5 else min(lows)
    swing_high = max(highs[-5:]) if len(highs) >= 5 else max(highs)

    if direction == "BUY":
        sl_swing = swing_low - sl_buffer
        sl_atr = entry - max_risk
        sl = max(sl_swing, sl_atr)
        risk = entry - sl
        if risk > max_risk:
            risk = max_risk
            sl = entry - risk
        if risk < min_risk:
            risk = min_risk
            sl = entry - risk
        tp1, tp2 = _strategic_tp_buy(entry, highs, risk, tp_buffer, tick)
    else:
        sl_swing = swing_high + sl_buffer
        sl_atr = entry + max_risk
        sl = min(sl_swing, sl_atr)
        risk = sl - entry
        if risk > max_risk:
            risk = max_risk
            sl = entry + risk
        if risk < min_risk:
            risk = min_risk
            sl = entry + risk
        tp1, tp2 = _strategic_tp_sell(entry, lows, risk, tp_buffer, tick)

    risk_denominator = max(0.0001, abs(entry - sl))
    rr_tp2 = abs(tp2 - entry) / risk_denominator

    return SetupResult(
        setups=setups,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        rr_tp2=rr_tp2,
        direction=direction,
        bias=bias,
        atr=atr_price,
    )


def _extract_series(candles: List[dict], key: str) -> List[float]:
    series: List[float] = []
    for candle in candles:
        value = candle.get(key)
        if value is None:
            continue
        try:
            series.append(float(value))
        except (TypeError, ValueError):
            continue
    if not series:
        return [0.0]
    return series


def _compute_atr(candles: List[dict], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges: List[float] = []
    prev_close = float(candles[0].get("close", 0.0) or 0.0)
    for candle in candles[1:]:
        high = float(candle.get("high", prev_close) or prev_close)
        low = float(candle.get("low", prev_close) or prev_close)
        close = float(candle.get("close", prev_close) or prev_close)
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
        prev_close = close
    if not true_ranges:
        return 0.0
    relevant = true_ranges[-period:]
    return sum(relevant) / len(relevant)


def _find_swing_highs_above(highs: List[float], entry: float, window: int = 2) -> List[float]:
    """Trouve les sommets (swing highs) au-dessus de l'entrée, triés du plus proche au plus loin."""
    if len(highs) < 5:
        return []
    candidates: List[float] = []
    for i in range(window, len(highs) - window):
        h = highs[i]
        if h <= entry:
            continue
        is_peak = all(highs[i] >= highs[j] for j in range(i - window, i + window + 1) if j != i)
        if is_peak:
            candidates.append(h)
    if not candidates:
        above = sorted([h for h in highs if h > entry])
        if above:
            seen: set[float] = set()
            for h in above:
                if h not in seen:
                    seen.add(h)
                    candidates.append(h)
    return sorted(set(candidates))


def _find_swing_lows_below(lows: List[float], entry: float, window: int = 2) -> List[float]:
    """Trouve les creux (swing lows) en dessous de l'entrée, triés du plus proche au plus loin."""
    if len(lows) < 5:
        return []
    candidates: List[float] = []
    for i in range(window, len(lows) - window):
        l = lows[i]
        if l >= entry:
            continue
        is_trough = all(lows[i] <= lows[j] for j in range(i - window, i + window + 1) if j != i)
        if is_trough:
            candidates.append(l)
    if not candidates:
        below = sorted([l for l in lows if l < entry], reverse=True)
        if below:
            seen: set[float] = set()
            for l in below:
                if l not in seen:
                    seen.add(l)
                    candidates.append(l)
    return sorted(set(candidates), reverse=True)


def _strategic_tp_buy(
    entry: float, highs: List[float], risk: float, tp_buffer: float, tick: float
) -> tuple[float, float]:
    """TP stratégiques BUY: juste avant les sommets déjà touchés (niveaux logiques)."""
    peaks = _find_swing_highs_above(highs, entry)
    if not peaks:
        return entry + risk, entry + 2 * risk
    tp1_candidate = peaks[0] - tp_buffer
    if tp1_candidate <= entry:
        return entry + risk, entry + 2 * risk
    tp1 = tp1_candidate
    tp2_fallback = entry + 2 * risk
    tp2 = tp2_fallback
    if len(peaks) >= 2 and peaks[1] - tp_buffer > tp1:
        tp2 = peaks[1] - tp_buffer
    if tp2 <= tp1:
        tp2 = tp1 + risk
    if (tp2 - entry) / max(risk, 0.0001) < 1.5:
        tp2 = tp2_fallback
    return tp1, tp2


def _strategic_tp_sell(
    entry: float, lows: List[float], risk: float, tp_buffer: float, tick: float
) -> tuple[float, float]:
    """TP stratégiques SELL: juste au-dessus des creux déjà touchés (niveaux logiques)."""
    troughs = _find_swing_lows_below(lows, entry)
    if not troughs:
        return entry - risk, entry - 2 * risk
    tp1_candidate = troughs[0] + tp_buffer
    if tp1_candidate >= entry:
        return entry - risk, entry - 2 * risk
    tp1 = tp1_candidate
    tp2_fallback = entry - 2 * risk
    tp2 = tp2_fallback
    if len(troughs) >= 2 and troughs[1] + tp_buffer < tp1:
        tp2 = troughs[1] + tp_buffer
    if tp2 >= tp1:
        tp2 = tp1 - risk
    if (entry - tp2) / max(risk, 0.0001) < 1.5:
        tp2 = tp2_fallback
    return tp1, tp2


def _average_range(highs: List[float], lows: List[float], lookback: int = 10) -> float:
    if not highs or not lows:
        return 0.0
    depth = min(len(highs), len(lows), lookback)
    if depth <= 0:
        return 0.0
    ranges = [max(0.0, highs[-i] - lows[-i]) for i in range(1, depth + 1)]
    return sum(ranges) / len(ranges)


def _infer_bias(closes: List[float], atr_price: float) -> Bias:
    if len(closes) < 5:
        return Bias.range
    lookback = min(len(closes), 20)
    delta = closes[-1] - closes[-lookback]
    threshold = max(atr_price * 0.2, closes[-1] * 0.0005)
    if delta > threshold:
        return Bias.up
    if delta < -threshold:
        return Bias.down
    return Bias.range


def infer_bias_from_candles(candles: List[dict]) -> Bias:
    """Calcule le bias (UP/DOWN/RANGE) à partir de bougies (H1, M15, etc.)."""
    if not candles:
        return Bias.range
    closes = _extract_series(candles, "close")
    if len(closes) < 5:
        return Bias.range
    atr_price = _compute_atr(candles)
    return _infer_bias(closes, atr_price)


def _infer_direction(bias: Bias, closes: List[float]) -> str:
    if bias == Bias.up:
        return "BUY"
    if bias == Bias.down:
        return "SELL"
    if len(closes) < 2:
        return "BUY"
    return "BUY" if closes[-1] >= closes[-2] else "SELL"


def _build_setups(direction: str, bias: Bias) -> List[str]:
    if bias == Bias.up:
        return ["Momentum haussier", "Pullback proche du swing bas"]
    if bias == Bias.down:
        return ["Momentum baissier", "Rejet du swing haut"]
    return []
