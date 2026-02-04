from __future__ import annotations

import json
from typing import Any, Dict

from app.config import get_settings
from app.infra.openai_client import OpenAIResult, generate_coach_message


def build_coach_prompt(payload: Dict[str, Any]) -> str:
    settings = get_settings()
    return (
        "Tu es un coach trading. Tu ne modifies jamais les chiffres fournis.\n"
        "Tu ne decises PAS BUY/SELL; tu expliques seulement.\n"
        f"Langue: {settings.coach_language}. Style: {settings.coach_mode}. Format Markdown.\n"
        "Reponds STRICTEMENT en JSON avec les champs:\n"
        "telegram_text, coach_bullets (liste), risk_note.\n"
        "Aucun texte hors JSON.\n"
        "telegram_text doit etre tres lisible, structuree, avec emojis.\n"
        "Structure telegram_text:\n"
        "1) Titre: ✅ GO / ❌ NO GO / 🟠 PRE-ALERTE\n"
        "2) 🧭 Contexte (H1 + M15) en 2-4 lignes max, vocabulaire simple\n"
        "3) 📰 News (moment + horizon + timing)\n"
        "4) 🎯 PLAN GO (GO uniquement, section centrale et evidente):\n"
        "   - ➡️ Entree: <prix>\n"
        "   - ⛔️ SL: <prix>\n"
        "   - 🎯 TP1: <prix>\n"
        "   - 🎯 TP2: <prix>\n"
        "   - Gestion: phrase simple (ex: TP1 => BE)\n"
        "5) 🧠 Pourquoi (4-6 bullets, courts, sans definir RR/spread/volatilite/bias)\n"
        "6) ⚠️ Conditions (pre-alerte uniquement)\n"
        "Interdit: section 'Explications simples', definitions RR/spread/volatilite/bias.\n"
        "Si un champ manque, ecrire 'non disponible' au lieu d'un placeholder.\n"
        "Emojis: GO=🚀✅🔥, NO_GO=🧱⛔️❌, PRE-ALERTE=🟠⏳👀\n"
        "Si news provider est mock, mentionner discretement: (calendrier mock).\n"
        "Interdit: promesse de gain, phrases floues, modifier chiffres.\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def generate_coach_message_from_payload(payload: Dict[str, Any]) -> OpenAIResult:
    return generate_coach_message(build_coach_prompt(payload))
