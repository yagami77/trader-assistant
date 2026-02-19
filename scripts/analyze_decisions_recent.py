#!/usr/bin/env python3
"""
Analyse les décisions récentes (signaux) : blocages, scores, raisons.
Usage: depuis la racine du projet :
  python scripts/analyze_decisions_recent.py
  python scripts/analyze_decisions_recent.py --hours 6
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Charger .env.local (DATABASE_PATH uniquement, sans importer app)
_root = Path(__file__).resolve().parents[1]
_env = _root / ".env.local"
_db_path = str(_root / "data" / "trader_assistant.db")
if _env.exists():
    for line in _env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_PATH="):
            _db_path = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
if not os.path.isabs(_db_path):
    _db_path = str(_root / _db_path)


def main(hours: int = 24):
    if not os.path.exists(_db_path):
        print(f"DB introuvable: {_db_path}")
        return
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    # Dernières N heures en UTC (ts_utc format ISO)
    cursor = conn.execute(
        """
        SELECT ts_utc, status, blocked_by, score_total, score_effective,
               direction, entry, sl, tp1, score_rules_json, reasons_json
        FROM signals
        WHERE ts_utc >= datetime('now', ?)
        ORDER BY ts_utc DESC
        """,
        (f"-{hours} hours",),
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print(f"Aucun signal dans les {hours} dernières heures.")
        return

    # Stats (accepter status en GO/no_go ou NO_GO)
    by_status = defaultdict(int)
    by_blocked = defaultdict(int)
    scores_no_go = []
    reasons_flat = []  # critères qui reviennent (0 pt / hors zone etc.)

    for r in rows:
        row = dict(r)
        status = (row.get("status") or "").strip()
        status_norm = "GO" if status.upper() == "GO" else "NO_GO"
        by_status[status_norm] += 1
        if status_norm == "NO_GO" and row.get("blocked_by"):
            by_blocked[row["blocked_by"]] += 1
        if status_norm == "NO_GO" and row.get("score_total") is not None:
            scores_no_go.append(row["score_total"])

        # Parser score_rules_json pour extraire les raisons (0 pt, hors zone, etc.)
        sr = row.get("score_rules_json")
        if sr and status_norm == "NO_GO":
            try:
                data = json.loads(sr)
                reasons = data.get("reasons") or []
                for line in reasons:
                    if isinstance(line, str) and ("0 pt" in line or "hors zone" in line or "manquant" in line.lower()):
                        reasons_flat.append(line.strip())
            except (json.JSONDecodeError, TypeError):
                pass

    total = len(rows)
    n_go = by_status.get("GO", 0)
    n_no_go = by_status.get("NO_GO", 0)

    print("=" * 60)
    print(f"  DÉCISIONS — Dernières {hours} h (total {total})")
    print("=" * 60)
    print(f"  GO:    {n_go}")
    print(f"  NO_GO: {n_no_go}")
    print()

    if n_no_go:
        print("--- Blocages NO_GO (blocked_by) ---")
        for reason, count in sorted(by_blocked.items(), key=lambda x: -x[1]):
            pct = 100 * count / n_no_go
            print(f"  {reason}: {count} ({pct:.0f}%)")
        print()

        if scores_no_go:
            avg = sum(scores_no_go) / len(scores_no_go)
            below_80 = sum(1 for s in scores_no_go if s < 80)
            below_85 = sum(1 for s in scores_no_go if s < 85)
            in_80_89 = sum(1 for s in scores_no_go if 80 <= s < 90)
            ge_90 = sum(1 for s in scores_no_go if s >= 90)
            print("--- Score total (NO_GO uniquement) ---")
            print(f"  Moyenne: {avg:.1f}")
            print(f"  < 80:   {below_80}  |  80–89: {in_80_89}  |  >= 90: {ge_90}")
            print(f"  < 85 (plafond Edge<28): {below_85}")
            print()

        if reasons_flat:
            def key_line(line):
                for sep in [" (+", " (0 pt)", " (-", " hors zone"]:
                    if sep in line:
                        return line.split(sep)[0].strip()
                return line[:60].strip()
            counted = Counter(key_line(l) for l in reasons_flat)
            print("--- Critères qui échouent le plus (0 pt / hors zone) ---")
            for reason, count in counted.most_common(15):
                print(f"  {count:3d}x  {reason}")
            print()

    print("=" * 60)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--hours", type=int, default=24, help="Dernières N heures")
    args = p.parse_args()
    main(hours=args.hours)
