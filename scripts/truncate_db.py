"""Vide toutes les tables de la base pour un nouveau suivi propre."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env.local", override=True)
sys.path.insert(0, str(REPO_ROOT))

from app.infra.db import truncate_all_tables

if __name__ == "__main__":
    truncate_all_tables()
    print("Tables tronquees.")
