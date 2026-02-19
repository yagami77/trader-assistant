"""
Analyse des trades du jour — comprendre les pertes.
1. Évalue les signaux GO en attente (signal_outcome_agent)
2. Liste les trades (GO + outcomes)
3. Analyse les pertes : score, setup, RR, timing...
Usage: python -m app.scripts.analyze_trades_today
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
_env_local = _REPO_ROOT / ".env.local"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local, override=True)
    except ImportError:
        pass

from zoneinfo import ZoneInfo

from app.config import get_settings
from app.infra.db import get_conn, init_db, get_trade_outcomes_today
from app.scripts.signal_outcome_agent import run_once


def _rr_tp1(entry: float, sl: float, tp1: float, direction: str) -> float:
    risk = abs(entry - sl)
    reward = abs(tp1 - entry)
    return reward / risk if risk > 0.01 else 0.0


def analyze_today(day_paris: str | None = None) -> dict:
    """Analyse les trades du jour et retourne un rapport."""
    tz = ZoneInfo("Europe/Paris")
    day = day_paris or datetime.now(tz).strftime("%Y-%m-%d")
    prefix = f"{day}%"

    init_db()

    # 1) Évaluer les signaux GO en attente (via bougies MT5) — optionnel si erreur
    n_eval = 0
    try:
        n_eval = run_once(get_settings().symbol_default, limit=20)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("signal_outcome_agent run_once: %s", e)

    conn = get_conn()

    # 2) GO du jour — avec outcomes si table signal_outcomes à jour
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.ts_utc, s.direction, s.entry, s.sl, s.tp1, s.tp2,
                   s.score_total, s.score_effective, s.blocked_by, s.decision_packet_json,
                   o.outcome, o.pnl_pts, o.outcome_ts_utc
            FROM signals s
            LEFT JOIN signal_outcomes o ON o.signal_id = s.id
            WHERE s.status = 'GO' AND s.telegram_sent = 1
              AND s.ts_utc LIKE ? AND s.entry IS NOT NULL AND s.sl IS NOT NULL
            ORDER BY s.ts_utc ASC
            """,
            (prefix,),
        ).fetchall()
    except Exception:
        # Schéma signal_outcomes obsolète : GO uniquement
        rows_raw = conn.execute(
            """
            SELECT s.id, s.ts_utc, s.direction, s.entry, s.sl, s.tp1, s.tp2,
                   s.score_total, s.score_effective, s.blocked_by, s.decision_packet_json
            FROM signals s
            WHERE s.status = 'GO' AND s.telegram_sent = 1
              AND s.ts_utc LIKE ? AND s.entry IS NOT NULL AND s.sl IS NOT NULL
            ORDER BY s.ts_utc ASC
            """,
            (prefix,),
        ).fetchall()
        rows = [dict(r) | {"outcome": None, "pnl_pts": None} for r in rows_raw]

    # 3) Outcomes bruts (trade_outcomes)
    outcomes_raw = get_trade_outcomes_today(day)

    # Si signal_outcomes vide, affecter outcomes_raw par ordre (1er GO → 1er outcome)
    outcomes_by_idx = outcomes_raw if outcomes_raw else []

    trades = []
    for i, row in enumerate(rows):
        r = dict(row)
        entry = float(r.get("entry") or 0)
        sl = float(r.get("sl") or 0)
        tp1 = float(r.get("tp1") or 0)
        direction = r.get("direction") or "BUY"
        outcome = r.get("outcome")
        pnl = r.get("pnl_pts")
        if pnl is None and i < len(outcomes_by_idx):
            pnl = outcomes_by_idx[i]
            outcome = "SL_HIT" if (pnl or 0) < 0 else ("TP1_HIT" if abs(pnl or 0) < 15 else "TP2_HIT")

        setup_type = "?"
        try:
            pj = r.get("decision_packet_json")
            if pj:
                p = json.loads(pj)
                st = p.get("state") or {}
                setup_type = st.get("setup_type", "?")
        except Exception:
            pass

        rr = _rr_tp1(entry, sl, tp1, direction)
        risk_pts = abs(entry - sl)

        trades.append({
            "ts": r.get("ts_utc", "")[:19],
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "risk_pts": round(risk_pts, 1),
            "rr_tp1": round(rr, 2),
            "score": r.get("score_total"),
            "setup_type": setup_type,
            "outcome": outcome or "OPEN",
            "pnl_pts": round(float(pnl), 1) if pnl is not None else None,
        })

    conn.close()

    # 4) Résumé
    wins = [t for t in trades if t["pnl_pts"] is not None and t["pnl_pts"] > 0]
    losses = [t for t in trades if t["pnl_pts"] is not None and t["pnl_pts"] <= 0]
    open_trades = [t for t in trades if t["outcome"] == "OPEN" or t["pnl_pts"] is None]

    total_pnl = sum(t["pnl_pts"] for t in trades if t["pnl_pts"] is not None)
    total_wins = sum(t["pnl_pts"] for t in wins)
    total_losses = sum(t["pnl_pts"] for t in losses)

    # 5) Analyse des pertes
    loss_analysis = []
    for t in losses:
        reasons = []
        if t.get("rr_tp1", 0) < 0.4:
            reasons.append("RR TP1 faible (< 0.4)")
        if t.get("score") is not None and t["score"] < 85:
            reasons.append(f"Score bas ({t['score']}/100)")
        if t.get("setup_type"):
            reasons.append(f"Setup: {t['setup_type']}")
        if t.get("risk_pts", 0) > 30:
            reasons.append(f"Risque élevé ({t['risk_pts']} pts)")
        loss_analysis.append({
            "ts": t["ts"],
            "direction": t["direction"],
            "pnl": t["pnl_pts"],
            "reasons": reasons or ["SL touché — revoir entrée / structure"],
        })

    return {
        "day": day,
        "n_evaluated": n_eval,
        "n_trades": len(trades),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "n_open": len(open_trades),
        "total_pnl": round(total_pnl, 1),
        "total_wins": round(total_wins, 1),
        "total_losses": round(total_losses, 1),
        "outcomes_raw": outcomes_raw,
        "trades": trades,
        "losses_detail": loss_analysis,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Analyse des trades du jour")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (défaut: aujourd'hui)")
    args = parser.parse_args()

    r = analyze_today(args.date)
    day = r["day"]

    print(f"\n{'='*50}")
    print(f"ANALYSE DES TRADES — {day}")
    print(f"{'='*50}\n")
    print(f"Signaux évalués (pending): {r['n_evaluated']}")
    print(f"Trades GO: {r['n_trades']} (gagnants: {r['n_wins']} | perdants: {r['n_losses']} | ouverts: {r['n_open']})")
    print(f"Total PnL: {r['total_pnl']} pts (gains: +{r['total_wins']} | pertes: {r['total_losses']})")
    print(f"\nOutcomes bruts: {r['outcomes_raw']}\n")

    if r["trades"]:
        print("--- Détail des trades ---")
        for t in r["trades"]:
            mark = "[+]" if (t.get("pnl_pts") or 0) > 0 else "[-]" if t.get("pnl_pts") is not None else "[?]"
            pnl_str = f"{t['pnl_pts']:+.1f}" if t.get("pnl_pts") is not None else "?"
            print(f"  {mark} {t['ts']} {t['direction']} entry={t['entry']:.1f} RR={t['rr_tp1']} score={t['score']} outcome={t['outcome']} PnL={pnl_str}")

    if r["losses_detail"]:
        print(f"\n--- Analyse des PERTES ({len(r['losses_detail'])}) ---")
        for la in r["losses_detail"]:
            print(f"\n  [-] {la['ts']} {la['direction']} PnL={la['pnl']} pts")
            for reason in la["reasons"]:
                print(f"     -> {reason}")

    print(f"\n{'='*50}\n")


if __name__ == "__main__":
    main()
