"""
Moteur de setup — style trader pro.
Utilise: structure (S/R, swing), timing d'entrée (breakout, pullback), contexte H1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.config import get_settings
from app.engines.entry_timing_engine import evaluate_entry_timing
from app.engines.structure_engine import analyze_structure


def _compute_atr(candles: list, period: int = 14) -> float:
    """ATR (Average True Range) sur N périodes."""
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


@dataclass(frozen=True)
class SetupResult:
    setups: List[str]
    entry: float
    sl: float
    tp1: float
    tp2: float
    rr_tp1: float
    rr_tp2: float
    direction: str
    bar_ts: Optional[str] = None
    setup_type: str = "ZONE_CONFIRMATION"
    timing_ready: bool = False
    structure_h1: str = "RANGE"
    entry_timing_reason: str = ""
    last_swing_low: Optional[float] = None
    last_swing_high: Optional[float] = None
    timing_step_zone_ok: Optional[bool] = None
    timing_step_pullback_ok: Optional[bool] = None
    timing_step_m5_ok: Optional[bool] = None


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
        from datetime import datetime, timezone
        ts = float(v)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if isinstance(v, str):
        return v.strip() or None
    return None


def _is_context_favorable(struct_h1, settings) -> bool:
    """Contexte favorable pour proposer TP2 bonus (trend, structure)."""
    return struct_h1.structure != "RANGE"


def _infer_direction_from_structure(structure: str, closes: List[float]) -> str:
    """Direction à partir de la structure H1 + momentum M15."""
    if structure == "BULLISH":
        return "BUY"
    if structure == "BEARISH":
        return "SELL"
    if len(closes) < 5:
        return "BUY"
    recent = closes[-5:]
    older = closes[-10:-5] if len(closes) >= 10 else closes[:-5]
    if not older:
        return "BUY"
    avg_recent = sum(recent) / len(recent)
    avg_older = sum(older) / len(older)
    if avg_recent > avg_older * 1.001:
        return "BUY"
    if avg_recent < avg_older * 0.999:
        return "SELL"
    return "BUY"


def detect_setups(
    candles_m15: List[dict],
    candles_h1: Optional[List[dict]] = None,
    current_price: Optional[float] = None,
    direction_override: Optional[str] = None,
    candles_m5: Optional[List[dict]] = None,
) -> SetupResult:
    """
    Setup détecté M15, confirmation sur M5 (1 barre M5 valide suffit).
    - candles_h1: contexte structure (bias)
    - current_price: tick pour savoir si on est dans la zone
    - direction_override: "BUY" ou "SELL" pour forcer la direction
    - candles_m5: confirmation M5 (1 rejet = bon moment)
    """
    if not candles_m15:
        return SetupResult(
            setups=[],
            entry=0.0,
            sl=0.0,
            tp1=0.0,
            tp2=0.0,
            rr_tp1=0.0,
            rr_tp2=0.0,
            direction="BUY",
            bar_ts=None,
            timing_step_zone_ok=None,
            timing_step_pullback_ok=None,
            timing_step_m5_ok=None,
        )
    settings = get_settings()
    atr = _compute_atr(candles_m15)
    struct_m15 = analyze_structure(candles_m15)
    struct_h1 = analyze_structure(candles_h1) if candles_h1 else struct_m15
    closes = _extract_series(candles_m15, "close")
    highs = _extract_series(candles_m15, "high")
    lows = _extract_series(candles_m15, "low")
    last = candles_m15[-1]
    close = float(last.get("close", 4660.0)) if closes else 4660.0
    bar_ts = _parse_bar_ts(last)
    direction = (direction_override or _infer_direction_from_structure(struct_h1.structure, closes)).upper()
    if direction not in ("BUY", "SELL"):
        direction = "BUY"
    swing_low = struct_m15.last_swing_low or (min(lows[-5:]) if len(lows) >= 5 else close - 20)
    swing_high = struct_m15.last_swing_high or (max(highs[-5:]) if len(highs) >= 5 else close + 20)
    buffer = max(2.0, (swing_high - swing_low) * 0.02) if swing_high > swing_low else 5.0
    sl_min = settings.sl_min_pts
    sl_max = settings.sl_max_pts
    tp1_min = settings.tp1_min_pts
    tp1_max = settings.tp1_max_pts
    rr_min_tp1 = getattr(settings, "rr_min_tp1", settings.rr_min)
    tp2_enable = getattr(settings, "tp2_enable_bonus", True)
    tp2_max_bonus = getattr(settings, "tp2_max_bonus_pts", 60.0)
    tp2_max_pts = getattr(settings, "tp2_max_pts", None)  # plafond distance entrée→TP2

    def _cap_bonus(b: float, r1: float) -> float:
        if tp2_max_pts is not None:
            return max(r1, min(tp2_max_pts, b))
        return b
    atr_margin = atr * 0.5

    if direction == "BUY":
        entry_structure = swing_low + buffer
        entry = round(entry_structure if abs(close - entry_structure) < 30 else close, 2)
        sl_raw = swing_low - buffer - atr_margin
        sl = round(min(sl_raw, entry - sl_min), 2)
        risk_raw = entry - sl
        risk = max(sl_min, min(sl_max, risk_raw))
        sl = round(entry - risk, 2)
        reward1 = max(tp1_min, min(tp1_max, risk * rr_min_tp1))
        tp1 = round(entry + reward1, 2)
        if tp2_enable and _is_context_favorable(struct_h1, settings):
            bonus = _cap_bonus(max(reward1, min(tp2_max_bonus, reward1 * 2)), reward1)
            tp2 = round(entry + bonus, 2)
        else:
            bonus = _cap_bonus(max(reward1 + 5, min(tp2_max_bonus, reward1 * 2)), reward1)
            tp2 = round(entry + bonus, 2)
    else:
        entry_structure = swing_high - buffer
        entry = round(entry_structure if abs(close - entry_structure) < 30 else close, 2)
        sl_raw = swing_high + buffer + atr_margin
        sl = round(max(sl_raw, entry + sl_min), 2)
        risk_raw = sl - entry
        risk = max(sl_min, min(sl_max, risk_raw))
        sl = round(entry + risk, 2)
        reward1 = max(tp1_min, min(tp1_max, risk * rr_min_tp1))
        tp1 = round(entry - reward1, 2)
        if tp2_enable and _is_context_favorable(struct_h1, settings):
            bonus = _cap_bonus(max(reward1, min(tp2_max_bonus, reward1 * 2)), reward1)
            tp2 = round(entry - bonus, 2)
        else:
            bonus = _cap_bonus(max(reward1 + 5, min(tp2_max_bonus, reward1 * 2)), reward1)
            tp2 = round(entry - bonus, 2)
    risk = abs(entry - sl)
    reward1_actual = abs(tp1 - entry)
    reward2 = abs(tp2 - entry)
    rr_tp1 = reward1_actual / risk if risk > 0.01 else 0.0
    rr_tp2 = reward2 / risk if risk > 0.01 else 0.0
    min_confirm = getattr(settings, "m5_rejection_min_bars", 2)
    entry_timing_mode = getattr(settings, "entry_timing_mode", "classic")
    pullback_req = getattr(settings, "pullback_require_for_setups", "BREAKOUT_RETEST,PULLBACK_SR")
    pullback_setups = [s.strip() for s in pullback_req.split(",") if s.strip()] if pullback_req else []
    timing = evaluate_entry_timing(
        candles_m15,
        direction,
        entry,
        struct_m15.last_swing_low,
        struct_m15.last_swing_high,
        current_price,
        atr=atr,
        candles_m5=candles_m5 or [],
        min_confirm_bars=min_confirm,
        entry_timing_mode=entry_timing_mode,
        pullback_min_ratio=getattr(settings, "pullback_min_ratio", 0.30),
        pullback_max_ratio=getattr(settings, "pullback_max_ratio", 0.50),
        pullback_require_setups=pullback_setups or ["BREAKOUT_RETEST", "PULLBACK_SR"],
        m5_rejection_lookback=getattr(settings, "m5_rejection_lookback_bars", 6),
    )
    if (
        timing.timing_ready
        and current_price is not None
        and timing.entry_zone_lo <= current_price <= timing.entry_zone_hi
    ):
        # Si le timing est prêt et que le prix est dans la zone, on ancre l'entrée sur le prix actuel
        entry = round(current_price, 2)
        risk = abs(entry - sl)
        risk = max(sl_min, min(sl_max, risk))
        if direction == "BUY":
            sl = round(entry - risk, 2)
        else:
            sl = round(entry + risk, 2)
        reward1 = max(tp1_min, min(tp1_max, risk * rr_min_tp1))
        if direction == "BUY":
            tp1 = round(entry + reward1, 2)
            if tp2_enable and _is_context_favorable(struct_h1, settings):
                bonus = _cap_bonus(max(reward1, min(tp2_max_bonus, reward1 * 2)), reward1)
                tp2 = round(entry + bonus, 2)
            else:
                bonus = _cap_bonus(max(reward1 + 5, min(tp2_max_bonus, reward1 * 2)), reward1)
                tp2 = round(entry + bonus, 2)
        else:
            tp1 = round(entry - reward1, 2)
            if tp2_enable and _is_context_favorable(struct_h1, settings):
                bonus = _cap_bonus(max(reward1, min(tp2_max_bonus, reward1 * 2)), reward1)
                tp2 = round(entry - bonus, 2)
            else:
                bonus = _cap_bonus(max(reward1 + 5, min(tp2_max_bonus, reward1 * 2)), reward1)
                tp2 = round(entry - bonus, 2)
        risk = abs(entry - sl)
        rr_tp1 = abs(tp1 - entry) / risk if risk > 0.01 else 0.0
        rr_tp2 = abs(tp2 - entry) / risk if risk > 0.01 else 0.0

    # Mode scalp : entrée au prix actuel SEULEMENT si dans la zone (évite entrées hasardeuses)
    if current_price is not None and getattr(settings, "mode_trading", "scalp") == "scalp":
        in_zone = timing.entry_zone_lo <= current_price <= timing.entry_zone_hi
        if in_zone and timing.timing_ready:
            entry = round(current_price, 2)
            risk = max(sl_min, min(sl_max, abs(entry - sl)))
            if direction == "BUY":
                sl = round(entry - risk, 2)
            else:
                sl = round(entry + risk, 2)
            reward1 = max(tp1_min, min(tp1_max, risk * rr_min_tp1))
            if direction == "BUY":
                tp1 = round(entry + reward1, 2)
                bonus = _cap_bonus(max(reward1 + 5, min(tp2_max_bonus, reward1 * 2)), reward1) if tp2_enable else reward1
                tp2 = round(entry + bonus, 2)
            else:
                tp1 = round(entry - reward1, 2)
                bonus = _cap_bonus(max(reward1 + 5, min(tp2_max_bonus, reward1 * 2)), reward1) if tp2_enable else reward1
                tp2 = round(entry - bonus, 2)
            risk = abs(entry - sl)
            rr_tp1 = abs(tp1 - entry) / risk if risk > 0.01 else 0.0
            rr_tp2 = abs(tp2 - entry) / risk if risk > 0.01 else 0.0
    setups = [timing.setup_type]
    if struct_h1.structure != "RANGE":
        setups.append(f"Structure H1 {struct_h1.structure}")
    if struct_m15.sr_levels:
        setups.append("S/R détectés")
    return SetupResult(
        setups=setups,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        rr_tp1=rr_tp1,
        rr_tp2=rr_tp2,
        direction=direction,
        bar_ts=bar_ts,
        setup_type=timing.setup_type,
        timing_ready=timing.timing_ready,
        structure_h1=struct_h1.structure,
        entry_timing_reason=timing.reason,
        last_swing_low=struct_m15.last_swing_low,
        last_swing_high=struct_m15.last_swing_high,
        timing_step_zone_ok=getattr(timing, "timing_step_zone_ok", None),
        timing_step_pullback_ok=getattr(timing, "timing_step_pullback_ok", None),
        timing_step_m5_ok=getattr(timing, "timing_step_m5_ok", None),
    )
