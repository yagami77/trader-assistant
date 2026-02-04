#!/usr/bin/env python3
"""Réinitialise le cooldown pour aujourd'hui (efface last_signal_key et last_ts)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.infra.db import get_conn


def main() -> None:
    day_paris = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.execute(
        "UPDATE state SET last_signal_key = NULL, last_ts = NULL WHERE day_paris = ?",
        (day_paris,),
    )
    conn.commit()
    n = cur.rowcount
    conn.close()
    print(f"Cooldown réinitialisé pour {day_paris} ({n} ligne(s) mise(s) à jour)")


if __name__ == "__main__":
    main()
