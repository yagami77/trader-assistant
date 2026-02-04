import json
import os
import sqlite3
from typing import Any, Dict, Optional

from app.config import get_settings


def get_conn() -> sqlite3.Connection:
    settings = get_settings()
    db_dir = os.path.dirname(settings.database_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            symbol TEXT NOT NULL,
            tf_signal TEXT NOT NULL,
            tf_context TEXT NOT NULL,
            status TEXT NOT NULL,
            blocked_by TEXT,
            direction TEXT,
            entry REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            rr_tp2 REAL,
            score_total INTEGER,
            score_effective INTEGER,
            telegram_sent INTEGER,
            telegram_error TEXT,
            telegram_latency_ms INTEGER,
            alert_key TEXT,
            score_rules_json TEXT,
            ai_enabled INTEGER,
            ai_output_json TEXT,
            ai_model TEXT,
            ai_input_tokens INTEGER,
            ai_output_tokens INTEGER,
            ai_cost_usd REAL,
            decision_packet_json TEXT,
            signal_key TEXT,
            reasons_json TEXT,
            message TEXT,
            data_latency_ms INTEGER,
            ai_latency_ms INTEGER
        );
        """
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(signals)").fetchall()}
    if "ts_local" in columns:
        conn.execute("DROP TABLE signals")
        conn.execute(
            """
            CREATE TABLE signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                symbol TEXT NOT NULL,
                tf_signal TEXT NOT NULL,
                tf_context TEXT NOT NULL,
                status TEXT NOT NULL,
                blocked_by TEXT,
                direction TEXT,
                entry REAL,
                sl REAL,
                tp1 REAL,
                tp2 REAL,
                rr_tp2 REAL,
                score_total INTEGER,
                score_effective INTEGER,
                telegram_sent INTEGER,
                telegram_error TEXT,
                telegram_latency_ms INTEGER,
                alert_key TEXT,
                score_rules_json TEXT,
                ai_enabled INTEGER,
                ai_output_json TEXT,
                ai_model TEXT,
                ai_input_tokens INTEGER,
                ai_output_tokens INTEGER,
                ai_cost_usd REAL,
                decision_packet_json TEXT,
                signal_key TEXT,
                reasons_json TEXT,
                message TEXT,
                data_latency_ms INTEGER,
                ai_latency_ms INTEGER
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(signals)").fetchall()}
    if "score_effective" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN score_effective INTEGER")
    if "telegram_sent" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN telegram_sent INTEGER")
    if "telegram_error" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN telegram_error TEXT")
    if "telegram_latency_ms" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN telegram_latency_ms INTEGER")
    if "alert_key" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN alert_key TEXT")
    if "ai_model" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN ai_model TEXT")
    if "ai_input_tokens" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN ai_input_tokens INTEGER")
    if "ai_output_tokens" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN ai_output_tokens INTEGER")
    if "ai_cost_usd" not in columns:
        conn.execute("ALTER TABLE signals ADD COLUMN ai_cost_usd REAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS state (
            day_paris TEXT PRIMARY KEY,
            daily_loss_amount REAL,
            daily_budget_amount REAL,
            last_signal_key TEXT,
            last_ts TEXT,
            consecutive_losses INTEGER
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage_daily (
            date TEXT PRIMARY KEY,
            tokens_in INTEGER,
            tokens_out INTEGER,
            cost_usd REAL,
            cost_eur REAL,
            n_calls INTEGER
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            symbol TEXT,
            decision TEXT,
            text TEXT,
            meta_json TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS signal_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER UNIQUE,
            ts_checked_utc TEXT,
            outcome_status TEXT,
            outcome_reason TEXT,
            hit_tp1 INTEGER,
            hit_tp2 INTEGER,
            hit_sl INTEGER,
            max_favorable_points REAL,
            max_adverse_points REAL,
            pnl_points REAL,
            horizon_minutes INTEGER,
            price_path_start_ts INTEGER,
            price_path_end_ts INTEGER
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_signal_id ON signal_outcomes(signal_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_ts_checked ON signal_outcomes(ts_checked_utc)"
    )
    conn.commit()
    conn.close()


def truncate_all_tables() -> None:
    """Vide toutes les tables (nouveau suivi propre)."""
    conn = get_conn()
    for table in ("signals", "signal_outcomes", "state", "ai_usage_daily", "ai_messages"):
        try:
            conn.execute(f"DELETE FROM {table}")
        except sqlite3.OperationalError:
            pass  # table may not exist
    conn.commit()
    conn.close()


def insert_signal(payload: Dict[str, Any]) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO signals (
            ts_utc, symbol, tf_signal, tf_context, status, blocked_by, direction,
            entry, sl, tp1, tp2, rr_tp2, score_total, score_effective,
            telegram_sent, telegram_error, telegram_latency_ms, alert_key, score_rules_json,
            ai_enabled, ai_output_json, ai_model, ai_input_tokens, ai_output_tokens, ai_cost_usd,
            decision_packet_json, signal_key,
            reasons_json, message, data_latency_ms, ai_latency_ms
        ) VALUES (
            :ts_utc, :symbol, :tf_signal, :tf_context, :status, :blocked_by, :direction,
            :entry, :sl, :tp1, :tp2, :rr_tp2, :score_total, :score_effective,
            :telegram_sent, :telegram_error, :telegram_latency_ms, :alert_key, :score_rules_json,
            :ai_enabled, :ai_output_json, :ai_model, :ai_input_tokens, :ai_output_tokens, :ai_cost_usd,
            :decision_packet_json, :signal_key,
            :reasons_json, :message, :data_latency_ms, :ai_latency_ms
        );
        """,
        payload,
    )
    conn.commit()
    conn.close()


def to_json(data: Optional[Dict[str, Any]]) -> Optional[str]:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=True)


def was_telegram_sent(signal_key: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT telegram_sent FROM signals WHERE signal_key = ? AND telegram_sent = 1 LIMIT 1",
        (signal_key,),
    ).fetchone()
    conn.close()
    return row is not None


def was_alert_sent(alert_key: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT alert_key FROM signals WHERE alert_key = ? LIMIT 1",
        (alert_key,),
    ).fetchone()
    conn.close()
    return row is not None


def get_ai_usage(date: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            COALESCE(tokens_in, 0) as tokens_in,
            COALESCE(tokens_out, 0) as tokens_out,
            COALESCE(cost_usd, 0) as cost_usd,
            COALESCE(cost_eur, 0) as cost_eur,
            COALESCE(n_calls, 0) as n_calls
        FROM ai_usage_daily
        WHERE date = ?
        """,
        (date,),
    ).fetchone()
    conn.close()
    if row is None:
        return {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "cost_eur": 0.0, "n_calls": 0}
    return dict(row)


def add_ai_usage(date: str, tokens_in: int, tokens_out: int, cost_usd: float, cost_eur: float) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO ai_usage_daily (date, tokens_in, tokens_out, cost_usd, cost_eur, n_calls)
        VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(date) DO UPDATE SET
            tokens_in = tokens_in + excluded.tokens_in,
            tokens_out = tokens_out + excluded.tokens_out,
            cost_usd = cost_usd + excluded.cost_usd,
            cost_eur = cost_eur + excluded.cost_eur,
            n_calls = n_calls + 1
        """,
        (date, tokens_in, tokens_out, cost_usd, cost_eur),
    )
    conn.commit()
    conn.close()


def insert_ai_message(ts_utc: str, symbol: str, decision: str, text: str, meta_json: Optional[str]) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO ai_messages (ts_utc, symbol, decision, text, meta_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ts_utc, symbol, decision, text, meta_json),
    )
    conn.commit()
    conn.close()


def upsert_signal_outcome(payload: Dict[str, Any]) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO signal_outcomes (
            signal_id, ts_checked_utc, outcome_status, outcome_reason,
            hit_tp1, hit_tp2, hit_sl,
            max_favorable_points, max_adverse_points, pnl_points,
            horizon_minutes, price_path_start_ts, price_path_end_ts
        ) VALUES (
            :signal_id, :ts_checked_utc, :outcome_status, :outcome_reason,
            :hit_tp1, :hit_tp2, :hit_sl,
            :max_favorable_points, :max_adverse_points, :pnl_points,
            :horizon_minutes, :price_path_start_ts, :price_path_end_ts
        )
        ON CONFLICT(signal_id) DO UPDATE SET
            ts_checked_utc=excluded.ts_checked_utc,
            outcome_status=excluded.outcome_status,
            outcome_reason=excluded.outcome_reason,
            hit_tp1=excluded.hit_tp1,
            hit_tp2=excluded.hit_tp2,
            hit_sl=excluded.hit_sl,
            max_favorable_points=excluded.max_favorable_points,
            max_adverse_points=excluded.max_adverse_points,
            pnl_points=excluded.pnl_points,
            horizon_minutes=excluded.horizon_minutes,
            price_path_start_ts=excluded.price_path_start_ts,
            price_path_end_ts=excluded.price_path_end_ts
        """,
        payload,
    )
    conn.commit()
    conn.close()
