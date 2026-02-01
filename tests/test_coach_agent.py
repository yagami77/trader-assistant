from app.agents.coach_agent import build_coach_output, can_call_ai, build_prompt
from app.infra.openai_client import OpenAIResult


def test_coach_agent_mock(monkeypatch):
    def fake_call(prompt: str):
        return OpenAIResult(
            text='{"telegram_text":"MSG","coach_bullets":["a","b"],"risk_note":"ok"}',
            input_tokens=100,
            output_tokens=50,
            latency_ms=12,
        )

    monkeypatch.setattr("app.agents.coach_agent.generate_coach_message_from_payload", fake_call)
    payload = {"decision": {"status": "GO"}, "packet": {}, "raw_message": "RAW"}
    output = build_coach_output(payload)
    assert output.telegram_text == "MSG"
    assert output.coach_bullets == ["a", "b"]
    assert output.input_tokens == 100
    assert output.model


def test_coach_agent_does_not_modify_decision_numbers(monkeypatch):
    def fake_call(prompt: str):
        return OpenAIResult(
            text='{"telegram_text":"MSG","coach_bullets":[],"risk_note":""}',
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )

    payload = {"decision": {"entry": 123.4, "sl": 120.0}, "packet": {}}
    monkeypatch.setattr("app.agents.coach_agent.generate_coach_message_from_payload", fake_call)
    build_coach_output(payload)
    assert payload["decision"]["entry"] == 123.4
    assert payload["decision"]["sl"] == 120.0


def test_budget_block(monkeypatch):
    from app.infra.db import add_ai_usage
    from app.config import get_settings
    import os
    from pathlib import Path

    os.environ["DATABASE_PATH"] = str(Path("/tmp/ai_budget_test.db"))
    get_settings.cache_clear()
    from app.infra.db import init_db
    init_db()
    settings = get_settings()
    add_ai_usage("2026-01-21", 0, 0, 0.0, settings.ai_max_cost_eur_per_day)
    prompt = build_prompt({"decision": {"status": "GO"}})
    assert can_call_ai("2026-01-21", prompt) is False
