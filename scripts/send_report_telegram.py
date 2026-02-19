"""Envoie le rapport des améliorations sur Telegram."""
from pathlib import Path
if (Path(__file__).resolve().parents[1] / ".env.local").exists():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infra.telegram_sender import TelegramSender

msg = """📋 RAPPORT — Améliorations et configuration actuelle

═══════════════════════════════════
✅ CE QUI A ÉTÉ FAIT
═══════════════════════════════════

🔹 SL (Stop Loss)
• Fenêtre : 10–12 pts (au lieu de 20–25)
• Placé de façon intelligente sur la structure (swing low/high)
• Objectif : limiter les pertes, améliorer le ratio gain/perte

🔹 EXTENSION_MOVE — Impulse Memory
• Problème : trop de blocages car la mémoire du mouvement initial sortait de la fenêtre courte (16 bougies)
• Solution : mémoire d'impulsion sur M15 (200 bougies)
  - Détection des grosses bougies (range >= ATR x 1.8)
  - reference_level = impulse_anchor si aligné
  - Exception retest : si setup BREAKOUT_RETEST ou PULLBACK_SR + timing OK + prix proche ancre → entrée autorisée

🔹 Agent Analyste
• Rapport quotidien Lun–Ven à 23h
• Profit/perte, analyse des pertes, recommandations
• Envoi automatique sur Telegram

🔹 Messages Suivi
• Situation toutes les 2 min, seulement si la situation change (anti-spam)
• Alerte proche SL : message uniquement quand <= 3 pts du SL

═══════════════════════════════════
🎯 STRATÉGIE — Deux TP
═══════════════════════════════════

• Objectif principal : TP1 (toujours visé)
• TP2 : bonus si le mouvement continue

• À venir (prévu, pas encore codé) :
  → Déplacer le SL à breakeven une fois TP1 touché
  → Sécurise le gain, laisse courir vers TP2 sans risque

═══════════════════════════════════
⚙️ CONFIG ACTUELLE
═══════════════════════════════════

SL_MIN_PTS=10 | SL_MAX_PTS=12
TP1: 7–15 pts | M15_FETCH_BARS=200
IMPULSE_ATR_MULT=1.8 | IMPULSE_RETEST_TOLERANCE_ATR=0.35
GO_MIN_SCORE=90
"""

r = TelegramSender().send_message(msg)
print("Sent:", r.sent, "Error:", r.error or "OK")
