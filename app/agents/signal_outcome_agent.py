from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class OutcomeResult:
    outcome_status: str
    outcome_reason: Optional[str]
    hit_tp1: int
    hit_tp2: int
    hit_sl: int
    max_favorable_points: Optional[float]
    max_adverse_points: Optional[float]
    pnl_points: Optional[float]
    price_path_start_ts: Optional[int]
    price_path_end_ts: Optional[int]


def _parse_ts(value: object) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1_000_000_000_000:
            return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            try:
                ts = float(raw)
                if ts > 1_000_000_000_000:
                    return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except ValueError:
                return None
    return None


def evaluate_outcome(
    candles: List[Dict[str, float]],
    direction: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    tick_size: float,
) -> OutcomeResult:
    if not candles:
        return OutcomeResult(
            outcome_status="UNKNOWN",
            outcome_reason="No candles",
            hit_tp1=0,
            hit_tp2=0,
            hit_sl=0,
            max_favorable_points=None,
            max_adverse_points=None,
            pnl_points=None,
            price_path_start_ts=None,
            price_path_end_ts=None,
        )

    direction = direction.upper()
    if direction not in {"BUY", "SELL"}:
        return OutcomeResult(
            outcome_status="UNKNOWN",
            outcome_reason="Invalid direction",
            hit_tp1=0,
            hit_tp2=0,
            hit_sl=0,
            max_favorable_points=None,
            max_adverse_points=None,
            pnl_points=None,
            price_path_start_ts=None,
            price_path_end_ts=None,
        )
    ts_list = [c.get("ts") or c.get("time_msc") or c.get("time") for c in candles]
    parsed = [_parse_ts(t) for t in ts_list]
    if any(p is None for p in parsed):
        return OutcomeResult(
            outcome_status="UNKNOWN",
            outcome_reason="Invalid candle timestamp",
            hit_tp1=0,
            hit_tp2=0,
            hit_sl=0,
            max_favorable_points=None,
            max_adverse_points=None,
            pnl_points=None,
            price_path_start_ts=None,
            price_path_end_ts=None,
        )

    # sort candles by timestamp
    ordered = sorted(zip(parsed, candles), key=lambda x: x[0])
    start_ts = int(ordered[0][0].timestamp())
    end_ts = int(ordered[-1][0].timestamp())

    max_fav = None
    max_adv = None
    hit_tp1 = 0
    hit_tp2 = 0
    hit_sl = 0
    outcome_status = "NO_HIT"
    outcome_reason = None

    for ts, candle in ordered:
        high = float(candle.get("high", 0.0))
        low = float(candle.get("low", 0.0))
        if direction == "BUY":
            fav = high - entry
            adv = low - entry
        else:
            fav = entry - low
            adv = high - entry

        max_fav = fav if max_fav is None else max(max_fav, fav)
        max_adv = adv if max_adv is None else min(max_adv, adv)

        # hit checks
        if direction == "BUY":
            hit_sl_now = low <= sl
            hit_tp1_now = high >= tp1
            hit_tp2_now = high >= tp2
        else:
            hit_sl_now = high >= sl
            hit_tp1_now = low <= tp1
            hit_tp2_now = low <= tp2

        if hit_sl_now and (hit_tp2_now or hit_tp1_now):
            hit_sl = 1
            outcome_status = "LOSS_SL"
            outcome_reason = "SL and TP hit same candle"
            break
        if hit_sl_now:
            hit_sl = 1
            outcome_status = "LOSS_SL"
            break
        if hit_tp2_now:
            hit_tp2 = 1
            outcome_status = "WIN_TP2"
            break
        if hit_tp1_now:
            hit_tp1 = 1
            outcome_status = "WIN_TP1"
            break

    # compute pnl
    pnl_points = None
    if tick_size > 0:
        if outcome_status == "WIN_TP2":
            pnl_points = abs(tp2 - entry) / tick_size
        elif outcome_status == "WIN_TP1":
            pnl_points = abs(tp1 - entry) / tick_size
        elif outcome_status == "LOSS_SL":
            pnl_points = -abs(entry - sl) / tick_size
        elif outcome_status == "NO_HIT":
            pnl_points = 0.0

    max_fav_points = max_fav / tick_size if tick_size > 0 and max_fav is not None else None
    max_adv_points = max_adv / tick_size if tick_size > 0 and max_adv is not None else None

    return OutcomeResult(
        outcome_status=outcome_status,
        outcome_reason=outcome_reason,
        hit_tp1=hit_tp1,
        hit_tp2=hit_tp2,
        hit_sl=hit_sl,
        max_favorable_points=max_fav_points,
        max_adverse_points=max_adv_points,
        pnl_points=pnl_points,
        price_path_start_ts=start_ts,
        price_path_end_ts=end_ts,
    )
