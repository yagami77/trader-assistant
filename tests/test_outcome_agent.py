from datetime import datetime, timezone, timedelta

from app.agents.signal_outcome_agent import evaluate_outcome
from app.infra.db import init_db, upsert_signal_outcome, get_conn
import os


def _candle(ts: datetime, high: float, low: float) -> dict:
    return {
        "ts": ts.isoformat(),
        "high": high,
        "low": low,
        "open": low,
        "close": high,
    }


def test_outcome_buy_tp1():
    now = datetime.now(timezone.utc)
    candles = [
        _candle(now, high=101, low=99),
        _candle(now + timedelta(minutes=1), high=106, low=100),
    ]
    result = evaluate_outcome(
        candles=candles,
        direction="BUY",
        entry=100,
        sl=95,
        tp1=105,
        tp2=110,
        tick_size=1.0,
    )
    assert result.outcome_status == "WIN_TP1"
    assert result.hit_tp1 == 1
    assert result.hit_sl == 0


def test_outcome_sell_sl_first():
    now = datetime.now(timezone.utc)
    candles = [
        _candle(now, high=111, low=101),  # SL hit first
        _candle(now + timedelta(minutes=1), high=109, low=89),
    ]
    result = evaluate_outcome(
        candles=candles,
        direction="SELL",
        entry=100,
        sl=110,
        tp1=90,
        tp2=80,
        tick_size=1.0,
    )
    assert result.outcome_status == "LOSS_SL"
    assert result.hit_sl == 1


def test_outcome_upsert(tmp_path):
    os.environ["DATABASE_PATH"] = str(tmp_path / "test.db")
    init_db()
    payload = {
        "signal_id": 1,
        "ts_checked_utc": datetime.now(timezone.utc).isoformat(),
        "outcome_status": "WIN_TP1",
        "outcome_reason": None,
        "hit_tp1": 1,
        "hit_tp2": 0,
        "hit_sl": 0,
        "max_favorable_points": 10.0,
        "max_adverse_points": -2.0,
        "pnl_points": 5.0,
        "horizon_minutes": 180,
        "price_path_start_ts": 1,
        "price_path_end_ts": 2,
    }
    upsert_signal_outcome(payload)
    conn = get_conn()
    row = conn.execute("SELECT outcome_status, pnl_points FROM signal_outcomes WHERE signal_id = 1").fetchone()
    conn.close()
    assert row["outcome_status"] == "WIN_TP1"
    assert float(row["pnl_points"]) == 5.0
