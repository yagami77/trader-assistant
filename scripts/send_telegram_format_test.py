#!/usr/bin/env python3
"""
Envoie des messages de test sur Telegram pour vérifier le format et les emojis.
Usage: python scripts/send_telegram_format_test.py
       ou: python scripts/send_telegram_format_test.py --delay 3
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_env_local = REPO_ROOT / ".env.local"
if _env_local.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_local)
    except ImportError:
        pass

# Ajouter le repo au path
sys.path.insert(0, str(REPO_ROOT))


def _messages() -> list[tuple[str, str]]:
    """Liste des (label, message) à envoyer."""
    return [
        ("A - GO", (
            "🟦🟦🟦 GO BUY NOW ✅\n\n"
            "XAUUSD (M15)\n\n"
            "💰 Prix actuel MT5 (live) : 5027.50\n\n"
            "➡️ Entrée : 5027.00\n"
            "⛔ SL : 5012.00\n"
            "🎯 TP1 : 5035.00 → Objectif principal (BE/fermé)\n"
            "🎯 TP2 : 5048.00 🎁 Bonus (optionnel)\n\n"
            "📋 SUIVI\n"
            "• TP1 atteint → réduire 50%, SL à l'entrée (BE)\n"
            "• TP2 atteint → fermer le reste\n"
            "• SL touché → sortie complète\n\n"
            "💎 Setup de qualité A+ ⚡\n"
            "Score global : 92/100\n\n"
            "Détails du score :\n"
            "• Confluence H1 alignée (+10)\n"
            "• Setup clair (+25)\n"
            "• RR TP1 >= 0.40 (+20)\n"
            "• Spread OK (<= 25) (+10)"
        )),
        ("B - MAINTIEN", (
            "🛫🟦 MAINTIEN BUY\n\n"
            "Prix: 5031.00 | Entrée: 5027.00\n"
            "SL: 5012.00 | TP1: 5035.00 | TP2: 5048.00\n"
            "Plan inchangé, structure OK, pas de mur proche, objectif TP maintenu."
        )),
        ("C - Suivi situation", (
            "📊 Suivi — Trade actif depuis 15 min\n\n"
            "Prix: 5031.00 | Entrée: 5027.00 | +4.0 pts\n"
            "SL: 5012.00 | TP1: 5035.00\n\n"
            "H1: BULLISH (avec nous) | M15: structure OK\n\n"
            "Score marché: 85/100\n\n"
            "Analyse: Tout va bien, on est dans le bon sens.\n\n"
            "➡️ On va vers TP1, laisser courir."
        )),
        ("D - ALERTE", (
            "⚠️ ALERTE — Attention mur / faiblesse\n\n"
            "Prix: 5032.00 | Entrée: 5027.00 | SL: 5012.00 | TP1: 5035.00\n"
            "Gain actuel ≈ 5.0 pts — sécurisation conseillée (BE / partiel)."
        )),
        ("E - TP1 atteint + BE", (
            "🎉 Bravo ! TP1 atteint\n\n"
            "✅ SL passé à Break-even — sécurisation en place\n\n"
            "🟦 BUY XAUUSD\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "➡️ Entrée : 5027.00\n"
            "⛔ SL (BE) : 5027.00\n"
            "🎯 TP2 : 5048.00\n\n"
            "💰 +8.0 pts réalisés (TP1)\n\n"
            "📈 On laisse courir vers TP2 !"
        )),
        ("F - Suivi post-TP1", (
            "📊 Suivi — Trade actif depuis 45 min\n\n"
            "Prix: 5042.00 | Entrée: 5027.00 | +15.0 pts\n"
            "SL: 5027.00 | TP1: 5035.00\n\n"
            "H1: BULLISH (avec nous) | M15: structure OK\n\n"
            "➡️ On va vers TP1, laisser courir."
        )),
        ("G - TP2 atteint", (
            "🎉 Bravo ! TP2 atteint\n\n"
            "📊 Résultat du trade: PROFIT +21.0 point\n\n"
            "Prix: 5048.00 | TP2: 5048.00\n"
            "Trade réussi, objectif bonus. À la prochaine !"
        )),
        ("H - SL touché", (
            "😔 SL touché — trade raté\n\n"
            "📊 Résultat du trade: PERTE — 15.0 point\n\n"
            "Prix: 5012.00 | SL: 5012.00\n"
            "On va récupérer dans la journée, on va faire mieux !\n"
            "Trade clôturé. Prochaine opportunité."
        )),
        ("I - Clôture manuelle (profit)", (
            "✅ Trade clôturé manuellement\n\n"
            "Résultat du trade : PROFIT +12.0 point\n\n"
            "Tu peux enchaîner sur un autre trade."
        )),
        ("J - Pré-alerte news", (
            "🟠 PRÉ-ALERTE XAUUSD (M15)\n"
            "📰 News: FOMC Minutes (HIGH)\n"
            "⏳ Moment pré-event — dans 25 min — horizon 60 min\n"
            "⚠️ Attention à la volatilité autour de la publication."
        )),
        ("K - NO GO", (
            "🟦🟦🟦 BUY — NO GO ❌\n\n"
            "XAUUSD (M15)\n"
            "Bloqué par : RR_TOO_LOW\n"
            "RR TP1 insuffisant pour le setup.\n\n"
            "Score global : 65/100\n\n"
            "Détails du score :\n"
            "• RR TP1 court (0 pt)"
        )),
        ("L - Données de retour", (
            "🟢 Données marché de retour — tu peux reprendre en temps réel."
        )),
        ("M - Résumé du jour", (
            "📊 Résumé du jour — 2 trade(s)\n\n"
            "Trade 1: +8.0 pts\n"
            "Trade 2: +10.5 pts\n\n"
            "Total: +18.5 point"
        )),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Envoie des messages de test format sur Telegram")
    parser.add_argument("--delay", type=float, default=2.0, help="Délai en secondes entre chaque message (défaut: 2)")
    parser.add_argument("--one", type=str, help="Envoyer uniquement le message dont le label contient cette chaîne (ex: TP1)")
    args = parser.parse_args()

    os.environ.setdefault("TELEGRAM_ENABLED", "true")
    from app.config import get_settings
    from app.infra.telegram_sender import TelegramSender

    s = get_settings()
    if not s.telegram_chat_id:
        print("ERREUR: TELEGRAM_CHAT_ID manquant dans .env.local")
        return 1
    if not s.telegram_bot_token:
        print("ERREUR: TELEGRAM_BOT_TOKEN manquant dans .env.local")
        return 1

    sender = TelegramSender()

    msgs = _messages()
    if args.one:
        msgs = [(l, m) for l, m in msgs if args.one.lower() in l.lower()]
        if not msgs:
            print(f"Aucun message ne contient '{args.one}'")
            return 1

    print(f"Envoi de {len(msgs)} message(s) sur Telegram...")
    for label, text in msgs:
        result = sender.send_message(text)
        if result.sent:
            print(f"  [OK] {label}")
        else:
            print(f"  [FAIL] {label} -- erreur: {result.error}")
        if args.delay > 0 and (label, text) != msgs[-1]:
            time.sleep(args.delay)

    print("Terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
