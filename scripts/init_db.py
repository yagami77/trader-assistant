"""Recreer toutes les tables de la base (utilise au demarrage du Core)."""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env.local", override=True)
sys.path.insert(0, str(REPO_ROOT))

from app.config import get_settings
from app.infra.db import init_db

if __name__ == "__main__":
    init_db()
    path = get_settings().database_path
    print(f"DB initialisee: {path}")
