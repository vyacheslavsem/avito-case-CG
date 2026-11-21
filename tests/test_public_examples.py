"""Tests mirroring the exact public examples from docs/tz/examples/.

These are the ONLY examples the organizers provide. We must pass them exactly.

Example 01-selection:
  - User: "Стол не шире метра, кресло и лампа. Таганрог. До 15 000 ₽ за всё."
  - Expected: ok status with valid options (table+chair+lamp, budget ≤ 15000, width_cm ≤ 100)

Example 02-clarification:
  - User: "Стол не шире метра, кресло и лампа. Таганрог."
  - Expected: clarify status with budget_rub question (budget is missing)
"""
import json
import os

from tests.cli import run_case

CATALOG = os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json")

# ── Exact public example 01-selection ──────────────────────────────────────

EXAMPLE_01_SELECTION = {
    "messages": [
        {
            "role": "user",
            "text": "Стол не шире метра, кресло и лампа. Таганрог. До 15 000 ₽ за всё."
        }
    ]
}

# ── Exact public example 02-clarification ─────────────────────────────────

EXAMPLE_02_CLARIFICATION = {
    "messages": [
        {
            "role": "user",
            "text": "Стол не шире метра, кресло и лампа. Таганрог."
        }
    ]
}


class TestPublicExample01Selection:
    """Reproduce the exact scenario from docs/tz/examples/01-selection/."""

    def test_example_01_returns_ok_status(self):
        """The public example 01 should return 'ok' (not clarify, not no_match)."""
        response = run_case(CATALOG, EXAMPLE_01_SELECTION)
        assert response["status"] == "ok", f"Expected 'ok', got {response['status']}"

    def test_example_01_has_options(self):
        """Response must have 1-3 options."""
        response = run_case(CATALOG, EXAMPLE_01_SELECTION)
        assert 1 <= len(response["options"]) <= 3

    def test_example_01_budget_constraint(self):
        """Each option must respect the 15 000 budget from the example."""
        response = run_case(CATALOG, EXAMPLE_01_SELECTION)
        for option in response["options"]:
            assert option["total_rub"] <= 15000, \
                f"Option total_rub {option['total_rub']} exceeds 15000 budget"

    def test_example_01_width_constraint(self):
        """Each table option must have width_cm ≤ 100 ('не шире метра')."""
        response = run_case(CATALOG, EXAMPLE_01_SELECTION)
        with open(CATALOG, encoding="utf-8") as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            for lid in option["listing_ids"]:
                l = catalog[lid]
                if l["category"] == "table":
                    width = l["attributes"].get("width_cm")
                    assert width is not None and width <= 100, \
                        f"Table {lid} has width {width}, must be ≤ 100"

    def test_example_01_all_three_categories(self):
        """Each option must contain exactly one table, one chair, one lamp."""
        response = run_case(CATALOG, EXAMPLE_01_SELECTION)
        with open(CATALOG, encoding="utf-8") as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            cats = set()
            for lid in option["listing_ids"]:
                cats.add(catalog[lid]["category"])
            assert cats == {"table", "chair", "lamp"}, \
                f"Option has categories {cats}, expected all three"

    def test_example_01_all_in_taganrog(self):
        """Every listing in every option must be in taganrog."""
        response = run_case(CATALOG, EXAMPLE_01_SELECTION)
        with open(CATALOG, encoding="utf-8") as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            for lid in option["listing_ids"]:
                assert catalog[lid]["city_id"] == "taganrog", \
                    f"Listing {lid} is in {catalog[lid]['city_id']}, not taganrog"

    def test_example_01_total_rub_exact(self):
        """total_rub must exactly equal the sum of price_rub from catalog."""
        response = run_case(CATALOG, EXAMPLE_01_SELECTION)
        with open(CATALOG, encoding="utf-8") as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            actual = sum(catalog[lid]["price_rub"] for lid in option["listing_ids"])
            assert option["total_rub"] == actual, \
                f"total_rub {option['total_rub']} != actual sum {actual}"


class TestPublicExample02Clarification:
    """Reproduce the exact scenario from docs/tz/examples/02-clarification/."""

    def test_example_02_returns_clarify_status(self):
        """The public example 02 should return 'clarify' (budget is missing)."""
        response = run_case(CATALOG, EXAMPLE_02_CLARIFICATION)
        assert response["status"] == "clarify", \
            f"Expected 'clarify', got {response['status']}"

    def test_example_02_has_budget_question(self):
        """The clarify response must ask for budget_rub."""
        response = run_case(CATALOG, EXAMPLE_02_CLARIFICATION)
        fields = {q["field"] for q in response["questions"]}
        assert "budget_rub" in fields, \
            f"Expected 'budget_rub' question, got fields: {fields}"

    def test_example_02_no_options(self):
        """Clarify status must not have options."""
        response = run_case(CATALOG, EXAMPLE_02_CLARIFICATION)
        assert "options" not in response, \
            "Clarify response must not contain options"

    def test_example_02_no_city_or_categories_questions(self):
        """City and categories are already known, so no question for them."""
        response = run_case(CATALOG, EXAMPLE_02_CLARIFICATION)
        fields = {q["field"] for q in response["questions"]}
        assert "city_id" not in fields, \
            "City is already known in the example, shouldn't ask again"
        assert "categories" not in fields, \
            "Categories are already known in the example, shouldn't ask again"


class TestFollowUpClarification:
    """Test the multi-turn flow that the checker simulates.
    
    After the first clarify (example 02), the checker adds:
    1. The bot's question as assistant message
    2. The user's answer as user message
    
    This simulates: "15 000 рублей"
    """

    def test_after_user_provides_budget(self):
        """User answers budget → should return 'ok' (not clarify)."""
        first_response = run_case(CATALOG, EXAMPLE_02_CLARIFICATION)
        question_text = first_response["questions"][0]["text"]

        # Simulate checker's behavior: add question as assistant, user's answer as user
        follow_up_request = {
            "messages": [
                {"role": "user", "text": EXAMPLE_02_CLARIFICATION["messages"][0]["text"]},
                {"role": "assistant", "text": question_text},
                {"role": "user", "text": "15 тысяч рублей"},
            ]
        }
        response = run_case(CATALOG, follow_up_request)
        assert response["status"] == "ok", \
            f"After user provides budget, expected 'ok', got {response['status']}"

    def test_follow_up_respects_budget(self):
        """After clarifying budget, options must respect the new budget."""
        first_response = run_case(CATALOG, EXAMPLE_02_CLARIFICATION)
        question_text = first_response["questions"][0]["text"]

        follow_up_request = {
            "messages": [
                {"role": "user", "text": EXAMPLE_02_CLARIFICATION["messages"][0]["text"]},
                {"role": "assistant", "text": question_text},
                {"role": "user", "text": "15 тысяч рублей"},
            ]
        }
        response = run_case(CATALOG, follow_up_request)
        for option in response["options"]:
            assert option["total_rub"] <= 15000, \
                f"Follow-up option total_rub {option['total_rub']} > 15000"
