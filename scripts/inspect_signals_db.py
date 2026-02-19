"""Inspect signals and state for a given trade (entry ~4937 SELL)."""
import os
import sqlite3
import sys
from pathlib import Path

# Load .env.local for DATABASE_PATH
_root = Path(__file__).resolve().parents[1]
_env = _root / ".env.local"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().replace('"', "").replace("'", ""))

db = os.environ.get("DATABASE_PATH", str(_root / "data" / "trader_assistant.db"))
if not Path(db).exists():
    print("DB not found:", db)
    sys.exit(1)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("=== Signaux GO (entry 4930-4945, SELL) ===")
cur = conn.execute(
    """
    SELECT ts_utc, symbol, status, direction, entry, sl, tp1, tp2, telegram_sent, signal_key
    FROM signals
    WHERE status = 'go' AND entry BETWEEN 4930 AND 4945
    ORDER BY ts_utc DESC
    LIMIT 25
    """
)
rows = cur.fetchall()
print(f"Count: {len(rows)}")
for r in rows:
    print(dict(r))

print("\n=== Tous signaux récents (today) ===")
cur2 = conn.execute(
    """
    SELECT ts_utc, status, direction, entry, tp1, tp2, telegram_sent
    FROM signals
    WHERE ts_utc >= date('now')
    ORDER BY ts_utc DESC
    LIMIT 30
    """
)
for r in cur2.fetchall():
    print(dict(r))

print("\n=== Table meta (suivi_sortie, etc.) ===")
cur3 = conn.execute("SELECT key, value FROM meta")
for r in cur3.fetchall():
    d = dict(r)
    if isinstance(d.get("value"), str) and len(d["value"]) > 200:
        d["value"] = d["value"][:200] + "..."
    print(d)

print("\n=== State (day_paris, active_*, last_*) ===")
cur4 = conn.execute(
    "SELECT day_paris, active_entry, active_started_ts, active_direction, last_setup_entry, last_setup_bar_ts, setup_confirm_count FROM state"
)
for r in cur4.fetchall():
    print(dict(r))

conn.close()
