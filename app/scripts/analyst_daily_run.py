"""
Agent Analyste — exécution quotidienne en fin de session (23h00-00h00 Paris).
Couche isolée : lit signals, outcomes, config. Propose améliorations. Envoie résumé Telegram.
S'exécute via : python -m app.scripts.analyst_daily_run
Ou planifié : Windows Task Scheduler à 23:00 (voir scripts/install_analyst_task.ps1)
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Charger .env.local
_REPO_ROOT = Path(__file__).resolve().parents[2]
_env_local = _REPO_ROOT / ".env.local"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local)
    except ImportError:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _is_in_market_close_window() -> bool:
    """True si on est entre 23h00 et 00h00 Paris (marché fermé), et Lun-Ven (pas weekend)."""
    tz = ZoneInfo("Europe/Paris")
    now = datetime.now(tz)
    if now.weekday() >= 5:  # 5=Sam, 6=Dim
        return False
    return now.hour == 23 or (now.hour == 0 and now.minute < 5)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Analyste — analyse quotidienne")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer l'exécution même hors fenêtre 23h-00h",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Nombre de jours à analyser (défaut: 7)",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Ne pas envoyer le résumé sur Telegram",
    )
    args = parser.parse_args()

    if not args.force and not _is_in_market_close_window():
        log.info(
            "Hors fenêtre 23h00-00h00 Paris. Utilisez --force pour exécuter quand même."
        )
        return 0

    log.info("Exécution Agent Analyste (jours=%d)", args.days)

    try:
        from app.agents.analyst_agent import run_analyst
        from app.config import get_settings
    except ImportError as e:
        log.error("Import: %s", e)
        return 1

    result = run_analyst(days=min(14, max(1, args.days)), save_report=True)
    log.info("Résumé: %s", result.summary[:200] if result.summary else "-")

    if result.recommendations:
        log.info("Recommandations: %d", len(result.recommendations))
        for r in result.recommendations[:5]:
            log.info("  - %s", r[:80] + "..." if len(r) > 80 else r)

    if not args.no_telegram and result.summary:
        settings = get_settings()
        if settings.telegram_enabled and settings.telegram_chat_id:
            try:
                from app.infra.telegram_sender import TelegramSender
                lines = [
                    "",
                    "📊 RAPPORT QUOTIDIEN — Agent Analyste",
                    "",
                    result.summary[:3200],
                ]
                if result.recommendations:
                    lines.extend([
                        "",
                        "═══════════════════════",
                        "🔧 AMÉLIORATIONS À FAIRE",
                        "═══════════════════════",
                        "",
                    ])
                    for i, rec in enumerate(result.recommendations[:5], 1):
                        lines.append("▶️ {}. {}".format(i, rec[:500]))
                        lines.append("")  # Retour à la ligne entre chaque
                lines.append("")
                msg = "\n".join(lines)
                r = TelegramSender().send_message(msg[:4000])  # Sécurité limite Telegram
                if r.sent:
                    log.info("Résumé envoyé sur Telegram")
                else:
                    log.warning("Telegram non envoyé: %s", r.error)
            except Exception as e:
                log.warning("Telegram: %s", e)

    return 0


if __name__ == "__main__":
    sys.exit(main())
