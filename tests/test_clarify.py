"""Test: clarification — missing budget, city, or categories."""
import json
import subprocess
import sys
import os
import pytest

RUN = os.path.join(os.path.dirname(__file__), "..", "run")
CATALOG = os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json")

# Missing budget → expect 'clarify' with budget_rub question
MISSING_BUDGET_REQUEST = {
    "messages": [
        {
            "role": "user",
            "text": "Стол не шире метра, кресло и лампа. Таганрог."
        }
    ]
}

# Missing everything → expect 'clarify' with all questions
EMPTY_REQUEST = {
    "messages": [
        {
            "role": "user",
            "text": "Хочу купить мебель."
        }
    ]
}


def _run(catalog_path, request):
    result = subprocess.run(
        [sys.executable, RUN, "--catalog", catalog_path],
        input=json.dumps(request, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"non-zero exit: {result.stderr}"
    return json.loads(result.stdout.strip())


class TestClarify:
    """Tests for the 'clarify' status."""

    def test_missing_budget(self):
        """Missing budget → clarify with budget_rub question."""
        response = _run(CATALOG, MISSING_BUDGET_REQUEST)
        assert response["status"] == "clarify"
        fields = {q["field"] for q in response["questions"]}
        assert "budget_rub" in fields

    def test_clarify_fields_unique(self):
        """Each field appears at most once in questions."""
        response = _run(CATALOG, MISSING_BUDGET_REQUEST)
        fields = [q["field"] for q in response["questions"]]
        assert len(fields) == len(set(fields))

    def test_clarify_no_options(self):
        """clarify response must not have options."""
        response = _run(CATALOG, MISSING_BUDGET_REQUEST)
        assert "options" not in response

    def test_clarify_questions_non_empty(self):
        """Each question has non-empty text."""
        response = _run(CATALOG, MISSING_BUDGET_REQUEST)
        for q in response["questions"]:
            assert len(q["text"]) > 0
            assert q["field"] in ("budget_rub", "city_id", "categories")
