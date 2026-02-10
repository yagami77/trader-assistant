from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from app.ai.coach import build_coach_prompt, generate_coach_message_from_payload
from app.config import get_settings
from app.infra.db import get_ai_usage
from app.infra.openai_client import OpenAIResult


@dataclass(frozen=True)
class CoachOutput:
    telegram_text: str
    coach_bullets: List[str]
    risk_note: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_eur: float
    model: str
    latency_ms: int


def _calc_cost(input_tokens: int, output_tokens: int) -> float:
    settings = get_settings()
    return (
        input_tokens / 1_000_000 * settings.ai_price_input_per_1m
        + output_tokens / 1_000_000 * settings.ai_price_output_per_1m
    )


def _calc_cost_eur(cost_usd: float) -> float:
    settings = get_settings()
    return cost_usd / settings.fx_eurusd


def _estimate_cost_eur(prompt: str) -> float:
    settings = get_settings()
    estimated_in = max(1, len(prompt) // 4)
    estimated_out = settings.ai_max_tokens_per_message
    cost_usd = _calc_cost(estimated_in, estimated_out)
    return _calc_cost_eur(cost_usd)


def can_call_ai(date: str, prompt: str) -> bool:
    settings = get_settings()
    usage = get_ai_usage(date)
    estimate = _estimate_cost_eur(prompt)
    return (usage["cost_eur"] + estimate) <= settings.ai_max_cost_eur_per_day


def build_prompt(payload: Dict[str, Any]) -> str:
    return build_coach_prompt(payload)


def _format_value(value: Any) -> str:
    if value is None:
        return "non disponible"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _enrich_telegram_text(text: str, payload: Dict[str, Any]) -> str:
    decision = payload.get("decision", {})
    packet = payload.get("packet", {})
    status = str(decision.get("status", "")).upper()
    lower = text.lower()
    lines: List[str] = [text.strip()] if text else []

    if status == "GO" and "🎯 plan" not in text:
        lines.extend(
            [
                "",
                "🎯 PLAN GO",
                f"➡️ Entrée: {_format_value(packet.get('proposed_entry'))}",
                f"⛔️ SL: {_format_value(packet.get('sl'))}",
                f"🎯 TP1: {_format_value(packet.get('tp1'))}",
                f"🎯 TP2: {_format_value(packet.get('tp2'))}",
                "Gestion: TP1 => BE",
            ]
        )

    if "explications simples" not in lower:
        lines.extend(
            [
                "",
                "🔍 Explications simples",
                f"- RR TP1: {_format_value(packet.get('rr_tp1'))}, TP2: {_format_value(packet.get('rr_tp2'))} (plus haut = mieux)",
                f"- Spread: {_format_value(packet.get('spread'))} (coût d'entrée), max {_format_value(packet.get('spread_max'))}",
                f"- Volatilité (ATR): {_format_value(packet.get('atr'))}, max {_format_value(packet.get('atr_max'))}",
                f"- Bias H1: {_format_value(packet.get('bias_h1'))} (direction dominante)",
            ]
        )

    return "\n".join(lines).strip()


def build_coach_output(payload: Dict[str, Any]) -> CoachOutput:
    result: OpenAIResult = generate_coach_message_from_payload(payload)
    raw = result.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"telegram_text": result.text, "coach_bullets": [], "risk_note": ""}
    cost = _calc_cost(result.input_tokens, result.output_tokens)
    cost_eur = _calc_cost_eur(cost)
    settings = get_settings()
    telegram_text = _enrich_telegram_text(parsed.get("telegram_text", ""), payload)
    return CoachOutput(
        telegram_text=telegram_text,
        coach_bullets=parsed.get("coach_bullets", []),
        risk_note=parsed.get("risk_note", ""),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=cost,
        cost_eur=cost_eur,
        model=settings.ai_model,
        latency_ms=result.latency_ms,
    )
