import io
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src import parser, runner, validator


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/tz/data/catalog.json"
REQUEST = (ROOT / "docs/tz/examples/01-selection/request.json").read_bytes()


def test_missing_key_fails_without_a_buyer_response():
    command = [sys.executable, str(ROOT / "run")] if os.name == "nt" else [str(ROOT / "run")]
    result = subprocess.run(
        [*command, "--catalog", str(CATALOG)], input=REQUEST, capture_output=True,
        env={**os.environ, "LLM_API_KEY": ""}, timeout=10,
    )
    assert result.returncode != 0
    assert result.stdout == b""
    assert b"LLM" in result.stderr
    assert b"Traceback" not in result.stderr


@pytest.mark.parametrize("budget,expected_status", [(None, "clarify"), (0, "no_match"), (15000, "ok")])
def test_rejected_response_is_a_technical_failure(monkeypatch, capfd, budget, expected_status):
    conditions = dict(city_id="taganrog", budget_rub=budget, categories=["table"], constraints={})
    monkeypatch.setattr(parser, "parse_request", lambda messages: conditions)
    statuses = []

    def reject(response, catalog, request, requirements):
        statuses.append(response["status"])
        return ["invalid test response"]

    monkeypatch.setattr(validator, "validate_response", reject)
    monkeypatch.setattr(sys, "argv", ["run", "--catalog", str(CATALOG)])
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(REQUEST)))
    assert runner.main() != 0
    assert statuses == [expected_status]
    assert capfd.readouterr().out == ""
