import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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
    # Corriger blocage DATA_OFF : alert_key enregistré sans envoi → permettre retry
    conn.execute(
        "UPDATE signals SET alert_key = NULL WHERE alert_key LIKE 'data_off:%' AND (telegram_sent IS NULL OR telegram_sent = 0)"
    )
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
    state_cols = {r["name"] for r in conn.execute("PRAGMA table_info(state)").fetchall()}
    for col, typ in [
        ("last_setup_direction", "TEXT"),
        ("last_setup_entry", "REAL"),
        ("last_setup_bar_ts", "TEXT"),
        ("setup_confirm_count", "INTEGER"),
        ("active_entry", "REAL"),
        ("active_sl", "REAL"),
        ("active_tp1", "REAL"),
        ("active_tp2", "REAL"),
        ("active_direction", "TEXT"),
        ("last_suivi_alerte_ts", "TEXT"),
        ("last_suivi_maintien_sent", "INTEGER"),
        ("active_started_ts", "TEXT"),
        ("last_suivi_situation_ts", "TEXT"),
        ("last_suivi_situation_signature", "TEXT"),
        ("last_trade_closed_ts", "TEXT"),
        # Système intelligent — state machine + contexte mémoire
        ("trade_state_machine", "TEXT"),
        ("trade_state_since_ts", "TEXT"),
        ("last_structure_type", "TEXT"),
        ("last_breakout_level", "REAL"),
        ("last_pullback_zone_lo", "REAL"),
        ("last_pullback_zone_hi", "REAL"),
        ("market_phase", "TEXT"),
        ("market_phase_since_ts", "TEXT"),
        # Break-even automatique après TP1
        ("active_be_applied", "INTEGER"),
        ("active_be_applied_ts_utc", "TEXT"),
        ("active_tp1_partial_pts", "REAL"),
        # Alerte invalidation (anti-fake)
        ("active_invalid_level", "REAL"),
        ("active_invalid_buffer_pts", "REAL"),
        ("last_invalidation_alert_ts", "TEXT"),
    ]:
        if col not in state_cols:
            conn.execute(f"ALTER TABLE state ADD COLUMN {col} {typ}")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
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
            signal_id INTEGER,
            ts_utc TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT,
            entry REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            outcome TEXT,
            pnl_pts REAL,
            outcome_ts_utc TEXT,
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        );
        """
    )
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


def get_last_analyze_ts() -> Optional[str]:
    """Dernier ts_utc d'une analyse (pour /runner/status)."""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT ts_utc FROM signals ORDER BY ts_utc DESC LIMIT 1",
            (),
        ).fetchone()
        conn.close()
        return row["ts_utc"] if row else None
    except Exception:
        return None


def get_last_telegram_sent_ts() -> Optional[str]:
    """Dernier ts_utc d'un signal envoyé sur Telegram (pour heartbeat)."""
    conn = get_conn()
    row = conn.execute(
        "SELECT ts_utc FROM signals WHERE telegram_sent = 1 ORDER BY ts_utc DESC LIMIT 1",
        (),
    ).fetchone()
    conn.close()
    return row["ts_utc"] if row else None


def get_last_go_sent_today(day_paris: str) -> Optional[dict]:
    """Dernier GO envoyé à Telegram aujourd'hui (entry, sl, tp1, tp2, ts_utc) pour éviter doublons."""
    conn = get_conn()
    row = conn.execute(
        """
        SELECT entry, sl, tp1, tp2, ts_utc
        FROM signals
        WHERE status = 'go' AND telegram_sent = 1 AND ts_utc LIKE ?
        ORDER BY ts_utc DESC LIMIT 1
        """,
        (f"{day_paris}%",),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "entry": float(row["entry"]) if row["entry"] is not None else None,
        "sl": float(row["sl"]) if row["sl"] is not None else None,
        "tp1": float(row["tp1"]) if row["tp1"] is not None else None,
        "tp2": float(row["tp2"]) if row["tp2"] is not None else None,
        "ts_utc": row["ts_utc"],
    }


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


def get_last_go_signal(symbol: str) -> Optional[dict]:
    """Dernier GO envoyé (telegram_sent=1) pour le suivi."""
    try:
        conn = get_conn()
        row = conn.execute(
            """
            SELECT ts_utc, direction, entry, sl, tp1, tp2
            FROM signals
            WHERE symbol = ? AND status = 'GO' AND telegram_sent = 1
            ORDER BY ts_utc DESC LIMIT 1
            """,
            (symbol,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


def _get_active_trade_for_day(conn, day_paris: str) -> Optional[dict]:
    """Trade actif pour un jour donné (interne)."""
    row = conn.execute(
        "SELECT active_entry, active_sl, active_tp1, active_tp2, active_direction, active_started_ts, "
        "active_be_applied, active_be_applied_ts_utc, active_tp1_partial_pts, "
        "active_invalid_level, active_invalid_buffer_pts, last_invalidation_alert_ts FROM state WHERE day_paris = ?",
        (day_paris,),
    ).fetchone()
    if row and row["active_entry"] is not None:
        return dict(row)
    return None


def get_active_trade(day_paris: str) -> Optional[dict]:
    """Trade actif en cours (aujourd'hui ou hier si ouvert en fin de journée)."""
    try:
        conn = get_conn()
        active = _get_active_trade_for_day(conn, day_paris)
        if active is not None:
            conn.close()
            return active
        # Trade pouvant être dans la ligne d'hier (ouvert en fin de session)
        try:
            from datetime import datetime, timedelta
            dt = datetime.strptime(day_paris, "%Y-%m-%d")
            yesterday = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
            active = _get_active_trade_for_day(conn, yesterday)
        except (ValueError, TypeError):
            pass
        conn.close()
        return active
    except Exception:
        return None


def set_active_trade(
    day_paris: str,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    direction: str,
    started_ts: Optional[str] = None,
    invalid_level: Optional[float] = None,
    invalid_buffer_pts: Optional[float] = None,
) -> None:
    conn = get_conn()
    conn.execute(
        """
        UPDATE state SET active_entry=?, active_sl=?, active_tp1=?, active_tp2=?, active_direction=?,
            last_suivi_alerte_ts=NULL, last_suivi_maintien_sent=0, active_started_ts=?, last_suivi_situation_ts=NULL,
            active_be_applied=0, active_be_applied_ts_utc=NULL,
            active_invalid_level=?, active_invalid_buffer_pts=?, last_invalidation_alert_ts=NULL
        WHERE day_paris=?
        """,
        (entry, sl, tp1, tp2, direction, started_ts, invalid_level, invalid_buffer_pts, day_paris),
    )
    conn.commit()
    conn.close()


def update_active_trade_sl_to_be(
    day_paris: str,
    entry: float,
    direction: str,
    offset_pts: float = 0.0,
    be_ts_utc: Optional[str] = None,
    tp1_partial_pts: Optional[float] = None,
) -> bool:
    """
    Passe le SL au break-even (entry ± offset). Idempotent : ne fait rien si be_applied=1.
    tp1_partial_pts: pts réalisés sur la portion clôturée au TP1 (si clôture partielle).
    Retourne True si la mise à jour a été faite, False si déjà appliqué.
    """
    dir_upper = (direction or "BUY").upper()
    if dir_upper == "BUY":
        new_sl = entry + offset_pts
    else:
        new_sl = entry - offset_pts
    ts = be_ts_utc or datetime.now(timezone.utc).isoformat()
    partial_val = tp1_partial_pts if tp1_partial_pts is not None else 0.0
    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE state SET active_sl=?, active_be_applied=1, active_be_applied_ts_utc=?,
            active_tp1_partial_pts=?
        WHERE day_paris=? AND (active_be_applied IS NULL OR active_be_applied=0)
        """,
        (new_sl, ts, partial_val if partial_val else 0.0, day_paris),
    )
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def clear_all_active_trades() -> int:
    """Efface le trade actif pour TOUS les jours. Retourne le nb de rows modifiées."""
    conn = get_conn()
    cur = conn.execute(
        "UPDATE state SET active_entry=NULL, active_sl=NULL, active_tp1=NULL, active_tp2=NULL, "
        "active_direction=NULL, last_suivi_alerte_ts=NULL, last_suivi_maintien_sent=0, active_started_ts=NULL, "
        "last_suivi_situation_ts=NULL, last_suivi_situation_signature=NULL, last_trade_closed_ts=NULL, "
        "active_be_applied=NULL, active_be_applied_ts_utc=NULL, active_tp1_partial_pts=NULL, "
        "active_invalid_level=NULL, active_invalid_buffer_pts=NULL, last_invalidation_alert_ts=NULL"
    )
    n = cur.rowcount if cur.rowcount >= 0 else 0
    conn.commit()
    conn.close()
    return n


def clear_active_trade(day_paris: str, closed_ts: Optional[str] = None, active_started_ts: Optional[str] = None) -> None:
    """Efface le trade actif. Si closed_ts fourni (TP/SL touché), enregistre pour cooldown prochain GO.
    Efface aujourd'hui, hier, et le jour de active_started_ts si fourni (évite trade résiduel)."""
    conn = get_conn()
    days_to_clear = [day_paris]
    try:
        from datetime import datetime, timedelta
        dt = datetime.strptime(day_paris, "%Y-%m-%d")
        yesterday = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        days_to_clear.append(yesterday)
        # Clôturer aussi le jour où le trade a démarré (si différent)
        if active_started_ts:
            try:
                start_dt = datetime.fromisoformat(active_started_ts.replace("Z", "+00:00"))
                start_day = start_dt.strftime("%Y-%m-%d")
                if start_day not in days_to_clear:
                    days_to_clear.append(start_day)
            except (ValueError, TypeError):
                pass
    except (ValueError, TypeError):
        pass
    for i, d in enumerate(days_to_clear):
        use_closed_ts = closed_ts and (i == 0)  # last_trade_closed_ts uniquement sur le jour courant
        if use_closed_ts:
            conn.execute(
                "UPDATE state SET active_entry=NULL, active_sl=NULL, active_tp1=NULL, active_tp2=NULL, active_direction=NULL, "
                "last_suivi_alerte_ts=NULL, last_suivi_maintien_sent=0, active_started_ts=NULL, last_suivi_situation_ts=NULL, "
                "last_trade_closed_ts=?, active_be_applied=NULL, active_be_applied_ts_utc=NULL, active_tp1_partial_pts=NULL, "
                "active_invalid_level=NULL, active_invalid_buffer_pts=NULL, last_invalidation_alert_ts=NULL WHERE day_paris=?",
                (closed_ts, d),
            )
        else:
            conn.execute(
                "UPDATE state SET active_entry=NULL, active_sl=NULL, active_tp1=NULL, active_tp2=NULL, active_direction=NULL, "
                "last_suivi_alerte_ts=NULL, last_suivi_maintien_sent=0, active_started_ts=NULL, last_suivi_situation_ts=NULL, "
                "last_suivi_situation_signature=NULL, active_be_applied=NULL, active_be_applied_ts_utc=NULL, active_tp1_partial_pts=NULL, "
                "active_invalid_level=NULL, active_invalid_buffer_pts=NULL, last_invalidation_alert_ts=NULL WHERE day_paris=?",
                (d,),
            )
    conn.commit()
    conn.close()
    # Pour que le prochain trade puisse recevoir un SORTIE, on efface le marqueur "déjà envoyé"
    clear_suivi_sortie_sent(day_paris)


def get_last_trade_closed_ts(day_paris: str) -> Optional[str]:
    """Dernier moment où un trade a été clôturé (TP/SL) pour appliquer le cooldown avant nouveau GO."""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT last_trade_closed_ts FROM state WHERE day_paris = ?",
            (day_paris,),
        ).fetchone()
        conn.close()
        return row["last_trade_closed_ts"] if row and row["last_trade_closed_ts"] else None
    except Exception:
        return None


def get_last_suivi_alerte_ts(day_paris: str) -> Optional[str]:
    """Dernier timestamp d'envoi d'une ALERTE suivi (pour relance après N min)."""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT last_suivi_alerte_ts FROM state WHERE day_paris = ?",
            (day_paris,),
        ).fetchone()
        conn.close()
        return row["last_suivi_alerte_ts"] if row and row["last_suivi_alerte_ts"] else None
    except Exception:
        return None


def was_suivi_maintien_sent(day_paris: str) -> bool:
    """MAINTIEN déjà envoyé pour le trade actif ?"""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT last_suivi_maintien_sent FROM state WHERE day_paris = ?",
            (day_paris,),
        ).fetchone()
        conn.close()
        return bool(row and row["last_suivi_maintien_sent"])
    except Exception:
        return False


def set_suivi_maintien_sent(day_paris: str) -> None:
    """Marque MAINTIEN comme envoyé."""
    conn = get_conn()
    conn.execute("UPDATE state SET last_suivi_maintien_sent=1 WHERE day_paris=?", (day_paris,))
    conn.commit()
    conn.close()


def set_last_suivi_alerte_ts(day_paris: str, ts_utc: str) -> None:
    """Enregistre l'envoi d'une ALERTE suivi."""
    conn = get_conn()
    conn.execute(
        "UPDATE state SET last_suivi_alerte_ts=? WHERE day_paris=?",
        (ts_utc, day_paris),
    )
    conn.commit()
    conn.close()


def set_last_invalidation_alert_ts(day_paris: str, ts_utc: str) -> None:
    """Enregistre l'envoi d'une alerte INVALIDATION (une fois par trade)."""
    conn = get_conn()
    conn.execute(
        "UPDATE state SET last_invalidation_alert_ts=? WHERE day_paris=?",
        (ts_utc, day_paris),
    )
    conn.commit()
    conn.close()


def get_last_suivi_situation_ts(day_paris: str) -> Optional[str]:
    """Dernier envoi d'un message « situation » suivi (pour espacement 15 min)."""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT last_suivi_situation_ts FROM state WHERE day_paris = ?",
            (day_paris,),
        ).fetchone()
        conn.close()
        return row["last_suivi_situation_ts"] if row and row["last_suivi_situation_ts"] else None
    except Exception:
        return None


def get_last_suivi_situation_signature(day_paris: str) -> Optional[str]:
    """Signature du dernier message situation envoyé (anti-spam : ne pas renvoyer si identique)."""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT last_suivi_situation_signature FROM state WHERE day_paris = ?",
            (day_paris,),
        ).fetchone()
        conn.close()
        return row["last_suivi_situation_signature"] if row and row["last_suivi_situation_signature"] else None
    except Exception:
        return None


def set_last_suivi_situation_ts(day_paris: str, ts_utc: str, signature: Optional[str] = None) -> None:
    """Enregistre l'envoi d'un message situation suivi (ts et signature pour anti-spam)."""
    conn = get_conn()
    if signature is not None:
        conn.execute(
            "UPDATE state SET last_suivi_situation_ts=?, last_suivi_situation_signature=? WHERE day_paris=?",
            (ts_utc, signature, day_paris),
        )
    else:
        conn.execute(
            "UPDATE state SET last_suivi_situation_ts=? WHERE day_paris=?",
            (ts_utc, day_paris),
        )
    conn.commit()
    conn.close()


def record_trade_outcome(day_paris: str, pnl_pips: float) -> None:
    """Enregistre le résultat d'un trade clôturé (pips, signés) pour le résumé du jour."""
    key = f"trade_outcomes_{day_paris}"
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        current = json.loads(row["value"]) if row and row["value"] else []
        current.append(round(pnl_pips, 1))
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, json.dumps(current)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_trade_outcomes_today(day_paris: str) -> list:
    """Liste des résultats (pips signés) des trades clôturés aujourd'hui."""
    key = f"trade_outcomes_{day_paris}"
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        conn.close()
        if row and row["value"]:
            return json.loads(row["value"])
    except Exception:
        pass
    return []


def get_stats_summary(day_paris: str) -> Dict[str, Any]:
    """Résumé du jour : GO/NO_GO, outcomes, budget (pour GET /stats/summary)."""
    prefix = f"{day_paris}"
    try:
        conn = get_conn()
        go_row = conn.execute(
            "SELECT COUNT(*) as n FROM signals WHERE ts_utc LIKE ? AND status = 'go'",
            (f"{prefix}%",),
        ).fetchone()
        no_go_row = conn.execute(
            "SELECT COUNT(*) as n FROM signals WHERE ts_utc LIKE ? AND status = 'no_go'",
            (f"{prefix}%",),
        ).fetchone()
        last_row = conn.execute(
            "SELECT ts_utc FROM signals WHERE ts_utc LIKE ? ORDER BY ts_utc DESC LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()
        state_row = conn.execute(
            "SELECT daily_loss_amount, daily_budget_amount FROM state WHERE day_paris = ?",
            (day_paris,),
        ).fetchone()
        conn.close()
        n_go = int(go_row["n"]) if go_row else 0
        n_no_go = int(no_go_row["n"]) if no_go_row else 0
        outcomes = get_trade_outcomes_today(day_paris)
        total_pips = round(sum(outcomes), 1) if outcomes else 0.0
        daily_loss = float(state_row["daily_loss_amount"]) if state_row and state_row["daily_loss_amount"] is not None else 0.0
        daily_budget = float(state_row["daily_budget_amount"]) if state_row and state_row["daily_budget_amount"] is not None else 20.0
        return {
            "day_paris": day_paris,
            "n_go": n_go,
            "n_no_go": n_no_go,
            "n_analyzes": n_go + n_no_go,
            "outcomes_pips": outcomes,
            "total_pips": total_pips,
            "daily_loss_amount": daily_loss,
            "daily_budget_amount": daily_budget,
            "last_signal_ts": last_row["ts_utc"] if last_row else None,
        }
    except Exception:
        return {
            "day_paris": day_paris,
            "n_go": 0,
            "n_no_go": 0,
            "n_analyzes": 0,
            "outcomes_pips": [],
            "total_pips": 0.0,
            "daily_loss_amount": 0.0,
            "daily_budget_amount": 20.0,
            "last_signal_ts": None,
        }


def get_last_suivi_sortie_active_started_ts(day_paris: str) -> Optional[str]:
    """active_started_ts du trade pour lequel on a déjà envoyé un message SORTIE (Bravo TP1/SL/TP2). Évite doublon."""
    key = f"suivi_sortie_sent_{day_paris}"
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        conn.close()
        return (row["value"] or "").strip() or None if row and row["value"] else None
    except Exception:
        return None


def set_last_suivi_sortie_sent(day_paris: str, active_started_ts: Optional[str]) -> None:
    """Marque qu'on a envoyé le message SORTIE pour ce trade (active_started_ts)."""
    key = f"suivi_sortie_sent_{day_paris}"
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (key, active_started_ts or ""),
    )
    conn.commit()
    conn.close()


def clear_suivi_sortie_sent(day_paris: str) -> None:
    """Efface le marqueur SORTIE envoyé (après clear_active_trade pour le jour)."""
    key = f"suivi_sortie_sent_{day_paris}"
    try:
        conn = get_conn()
        conn.execute("DELETE FROM meta WHERE key = ?", (key,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def was_daily_summary_sent(day_paris: str) -> bool:
    """Résumé du jour déjà envoyé pour cette date ?"""
    key = f"daily_summary_sent_{day_paris}"
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        conn.close()
        return bool(row and row["value"] == "1")
    except Exception:
        return False


def set_daily_summary_sent(day_paris: str) -> None:
    """Marque le résumé du jour comme envoyé."""
    key = f"daily_summary_sent_{day_paris}"
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (key, "1"),
    )
    conn.commit()
    conn.close()


def was_data_off_alert_sent_today(day_paris: str) -> bool:
    """True si une alerte DATA_OFF a été envoyée aujourd'hui (pour envoyer "données de retour" une fois)."""
    key = f"data_off_alert_sent_{day_paris}"
    try:
        conn = get_conn()
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        conn.close()
        return bool(row and row["value"] == "1")
    except Exception:
        return False


def set_data_off_alert_sent(day_paris: str) -> None:
    """Marque qu'une alerte DATA_OFF a été envoyée aujourd'hui."""
    key = f"data_off_alert_sent_{day_paris}"
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (key, "1"),
    )
    conn.commit()
    conn.close()


def clear_data_off_alert_sent(day_paris: str) -> None:
    """Réinitialise après envoi du message « données de retour »."""
    key = f"data_off_alert_sent_{day_paris}"
    conn = get_conn()
    conn.execute("DELETE FROM meta WHERE key = ?", (key,))
    conn.commit()
    conn.close()


def get_recent_signals(symbol: str, limit: int = 20) -> list:
    """Derniers signaux pour contexte historique (niveaux testés, GO/NO_GO)."""
    try:
        conn = get_conn()
        rows = conn.execute(
            """
            SELECT ts_utc, status, blocked_by, direction, entry, sl, tp1, score_total
            FROM signals
            WHERE symbol = ?
            ORDER BY ts_utc DESC
            LIMIT ?
            """,
            (symbol, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_analyst_signals(days: int = 7, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Signaux des N derniers jours pour l'agent analyste (GO/NO_GO, blocked_by, score, setup)."""
    try:
        from zoneinfo import ZoneInfo
        sym = symbol or get_settings().symbol_default
        tz = ZoneInfo("Europe/Paris")
        end = datetime.now(tz).date()
        start = end - timedelta(days=days)
        conn = get_conn()
        rows = []
        for i in range(days + 1):
            d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            prefix = f"{d}%"
            for row in conn.execute(
                """
                SELECT ts_utc, status, blocked_by, direction, entry, sl, tp1, score_total, decision_packet_json
                FROM signals
                WHERE symbol = ? AND ts_utc LIKE ?
                ORDER BY ts_utc ASC
                """,
                (sym, prefix),
            ).fetchall():
                r = dict(row)
                setup_type = "?"
                try:
                    pj = r.get("decision_packet_json")
                    if pj:
                        p = json.loads(pj)
                        st = p.get("state") or {}
                        setup_type = st.get("setup_type", "?")
                except Exception:
                    pass
                r["setup_type"] = setup_type
                r["day_paris"] = d
                rows.append(r)
        conn.close()
        return rows
    except Exception:
        return []


def get_analyst_outcomes_by_day(days: int = 7) -> Dict[str, List[float]]:
    """Outcomes (pips) par jour pour les N derniers jours."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Paris")
        end = datetime.now(tz).date()
        result: Dict[str, List[float]] = {}
        conn = get_conn()
        for i in range(days + 1):
            d = (end - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"trade_outcomes_{d}"
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            if row and row["value"]:
                result[d] = json.loads(row["value"])
            else:
                result[d] = []
        conn.close()
        return result
    except Exception:
        return {}


def save_analyst_report(report_json: str) -> None:
    """Sauvegarde le dernier rapport analyste."""
    conn = get_conn()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (f"ai_analyst_report_{ts}", report_json),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('ai_analyst_last_report', ?)",
        (report_json,),
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
