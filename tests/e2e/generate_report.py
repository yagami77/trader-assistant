from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from tests.e2e.helpers import (
    analyze,
    count_signals,
    fetch_signal_rows,
    measure_latency,
    restore_news,
    run_api,
    set_state_budget_reached,
    write_news_with_event,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "REPORT_SPRINT2.md"


def _detect_api_port() -> str:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    match = re.search(r'-\\s*\"(\\d+):8000\"', compose)
    return match.group(1) if match else "8000"


def _health_check(base_url: str) -> dict:
    resp = httpx.get(f"{base_url}/health", timeout=2.0)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    port = _detect_api_port()
    base_url = os.environ.get("REPORT_BASE_URL", f"http://localhost:{port}")
    health = _health_check(base_url)

    unit_output = ""
    unit_log = REPO_ROOT / "tests" / "e2e" / "unit_tests_output.txt"
    if unit_log.exists():
        unit_output = unit_log.read_text(encoding="utf-8").strip()

    scenarios = []
    status = "PASS"

    def _record(name: str, response: dict, db_rows: list) -> None:
        scenarios.append(
            {
                "name": name,
                "response": response,
                "db_rows": db_rows,
            }
        )

    # OUT_OF_SESSION
    with run_api(
        {"ALWAYS_IN_SESSION": "false", "MOCK_SERVER_TIME_UTC": "2026-01-21T08:00:00+00:00"}
    ) as (url, db_path):
        response = analyze(url)
        _record("OUT_OF_SESSION", response, fetch_signal_rows(db_path, 1))

    # NEWS_LOCK
    now_utc = datetime(2026, 1, 21, 14, 45, tzinfo=timezone.utc)
    backup = write_news_with_event(now_utc + timedelta(minutes=10))
    try:
        with run_api(
            {"ALWAYS_IN_SESSION": "true", "MOCK_SERVER_TIME_UTC": now_utc.isoformat()}
        ) as (url, db_path):
            response = analyze(url)
            _record("NEWS_LOCK", response, fetch_signal_rows(db_path, 1))
    finally:
        restore_news(backup)

    # DUPLICATE_SIGNAL
    with run_api(
        {"ALWAYS_IN_SESSION": "true", "MOCK_SERVER_TIME_UTC": "2026-01-21T09:00:00+00:00"}
    ) as (url, db_path):
        before = count_signals(db_path)
        first = analyze(url)
        after_first = count_signals(db_path)
        second = analyze(url)
        after_second = count_signals(db_path)
        _record("DUPLICATE_SIGNAL (1st)", first, fetch_signal_rows(db_path, 1))
        _record(
            "DUPLICATE_SIGNAL (2nd)",
            second,
            fetch_signal_rows(db_path, 2),
        )
        scenarios.append(
            {
                "name": "DUPLICATE_SIGNAL (counts)",
                "response": {
                    "before": before,
                    "after_first": after_first,
                    "after_second": after_second,
                },
                "db_rows": [],
            }
        )

    # RR_TOO_LOW
    with run_api({"ALWAYS_IN_SESSION": "true", "RR_MIN": "10.0"}) as (url, db_path):
        response = analyze(url)
        _record("RR_TOO_LOW", response, fetch_signal_rows(db_path, 1))

    # DAILY_BUDGET_REACHED
    with run_api(
        {"ALWAYS_IN_SESSION": "true", "MOCK_SERVER_TIME_UTC": "2026-01-21T09:00:00+00:00"}
    ) as (url, db_path):
        set_state_budget_reached(db_path, "2026-01-21")
        response = analyze(url)
        _record("DAILY_BUDGET_REACHED", response, fetch_signal_rows(db_path, 1))

    # DATA_OFF
    with run_api({"ALWAYS_IN_SESSION": "true", "MOCK_PROVIDER_FAIL": "true"}) as (url, db_path):
        response = analyze(url)
        _record("DATA_OFF", response, fetch_signal_rows(db_path, 1))

    latency = measure_latency(base_url, calls=10)

    for scenario in scenarios:
        decision = scenario["response"].get("decision")
        if not decision:
            continue
        blocked = decision["blocked_by"]
        if scenario["name"] != "DUPLICATE_SIGNAL (1st)" and blocked is None:
            status = "FAIL"

    report_lines = [
        "# REPORT_SPRINT2",
        "",
        f"## Résumé",
        f"- Status: **{status}**",
        f"- API port détecté: `{port}`",
        f"- /health: `{json.dumps(health)}`",
        "",
        "## Tests unitaires",
        "```",
        unit_output or "Aucune sortie capturée.",
        "```",
        "",
        "## Scénarios E2E",
        "- Toutes les lectures DB utilisent `ORDER BY id DESC LIMIT N`.",
    ]

    for scenario in scenarios:
        report_lines.extend(
            [
                f"### {scenario['name']}",
                "Réponse:",
                "```json",
                json.dumps(scenario["response"], ensure_ascii=False, indent=2),
                "```",
                "DB (dernieres lignes):",
                "```json",
                json.dumps(scenario["db_rows"], ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )

    report_lines.extend(
        [
            "## Performance /analyze (10 appels)",
            f"- min: {latency['min']:.4f}s",
            f"- avg: {latency['avg']:.4f}s",
            f"- max: {latency['max']:.4f}s",
            "",
        ]
    )

    REPORT_PATH.write_text("\n".join(report_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
