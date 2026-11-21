"""Unit tests for src/validator.py.

Tests the validate_response function directly (no subprocess).
Covers:
  - ok / clarify / no_match status validation
  - option validation: IDs, categories, total_rub, budget
  - city checking
  - attribute constraint checking
  - edge cases: empty options, duplicates, unknown IDs
"""
import sys
import os
import json
import copy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.validator import validate_response, validate_response_shape


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def catalog():
    """Load the real test catalog."""
    catalog_path = os.path.join(
        os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json"
    )
    with open(catalog_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def listing_map(catalog):
    """Build {id: listing} map from catalog."""
    return {l["id"]: l for l in catalog}


# Real IDs from catalog
TABLE_ID = "demo-1-1-07"   # t07 doesn't exist — using demo-1-1-07 (table, width_cm=60)
CHAIR_ID = "demo-1-2-03"   # chair, adjustable_height=true
LAMP_ID = "demo-1-3-03"    # lamp, color_temperature_k=4000

# Common requirements used across tests
FULL_REQUIREMENTS = {
    "city_id": "taganrog",
    "budget_rub": 15000,
    "categories": ["table", "chair", "lamp"],
    "constraints": {},
}

PARTIAL_REQUIREMENTS = {
    "city_id": "taganrog",
    "budget_rub": None,
    "categories": ["table"],
    "constraints": {},
}


# ── Helpers ───────────────────────────────────────────────────────

def _valid_ok_response(listing_ids, total_rub, explanation="Good option"):
    """Build a structurally valid 'ok' response."""
    return {
        "status": "ok",
        "options": [
            {
                "listing_ids": listing_ids,
                "total_rub": total_rub,
                "explanation": explanation,
            }
        ],
    }


def _valid_clarify_response(questions):
    """Build a structurally valid 'clarify' response."""
    return {
        "status": "clarify",
        "questions": questions,
    }


def _valid_no_match_response(message="No matching kit found."):
    """Build a structurally valid 'no_match' response."""
    return {
        "status": "no_match",
        "message": message,
    }


# ── Status validation ────────────────────────────────────────────

class TestStatusValidation:
    """Validate overall response structure per status."""

    def test_ok_status_valid(self, listing_map):
        """Valid ok response returns no errors."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        actual = t["price_rub"] + c["price_rub"]
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        assert errors == []

    def test_clarify_status_valid(self):
        """Valid clarify response returns no errors."""
        response = _valid_clarify_response([{"field": "budget_rub", "text": "Укажите бюджет"}])
        errors = validate_response(response, [], {}, PARTIAL_REQUIREMENTS)
        assert errors == []

    def test_no_match_status_valid(self):
        """Valid no_match response returns no errors."""
        response = _valid_no_match_response("Не хватает бюджета.")
        errors = validate_response(response, [], FULL_REQUIREMENTS, FULL_REQUIREMENTS)
        assert errors == []

    def test_unknown_status(self):
        """Unknown status produces an error."""
        response = {"status": "invalid_status"}
        errors = validate_response(response, [], {}, {})
        assert any("Unknown status" in e for e in errors)

    def test_clarify_empty_questions(self):
        """Clarify with empty questions array → error."""
        response = {"status": "clarify", "questions": []}
        errors = validate_response(response, [], {}, {})
        assert any("non-empty questions" in e for e in errors)

    def test_clarify_missing_questions(self):
        """Clarify without questions key → error."""
        response = {"status": "clarify"}
        errors = validate_response(response, [], {}, {})
        assert any("non-empty questions" in e for e in errors)

    def test_no_match_empty_message(self):
        """No_match with empty message → error."""
        response = {"status": "no_match", "message": ""}
        errors = validate_response(response, [], {}, {})
        assert any("non-empty message" in e for e in errors)

    def test_no_match_missing_message(self):
        """No_match without message key → error."""
        response = {"status": "no_match"}
        errors = validate_response(response, [], {}, {})
        assert any("non-empty message" in e for e in errors)


# ── Option validation: listing_ids ───────────────────────────────

class TestOptionListingIds:
    """Validate listing_ids field in ok options."""

    def test_empty_listing_ids(self, listing_map):
        """Empty listing_ids array → error."""
        response = _valid_ok_response([], 0)
        req = {"city_id": "taganrog", "budget_rub": 10000, "categories": ["table"]}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("listing_ids must not be empty" in e for e in errors)

    def test_duplicate_ids(self, listing_map):
        """Duplicate listing IDs → error."""
        response = _valid_ok_response([TABLE_ID, TABLE_ID, CHAIR_ID], 10000)
        req = {"city_id": "taganrog", "budget_rub": 20000, "categories": ["table", "chair"]}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("duplicate listing_ids" in e for e in errors)

    def test_unknown_listing_id(self, listing_map):
        """Listing ID not in catalog → error."""
        response = _valid_ok_response([TABLE_ID, "nonexistent-id", CHAIR_ID], 10000)
        req = {"city_id": "taganrog", "budget_rub": 20000, "categories": ["table", "chair"]}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("nonexistent-id" in e and "not in catalog" in e for e in errors)

    def test_single_valid_listing(self, listing_map):
        """Single valid listing ID → no listing-related errors."""
        t = listing_map[TABLE_ID]
        response = _valid_ok_response([TABLE_ID], t["price_rub"])
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        # Filter only listing_ids errors
        id_errors = [e for e in errors if "listing_ids" in e or "listing_id" in e]
        assert id_errors == []


# ── Option validation: categories ────────────────────────────────

class TestOptionCategories:
    """Validate that options cover exactly the requested categories."""

    def test_categories_match(self, listing_map):
        """Option with correct categories → no error."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        l = listing_map[LAMP_ID]
        actual = t["price_rub"] + c["price_rub"] + l["price_rub"]
        response = _valid_ok_response([TABLE_ID, CHAIR_ID, LAMP_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair", "lamp"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        cat_errors = [e for e in errors if "categories" in e]
        assert cat_errors == []

    def test_missing_category(self, listing_map):
        """Option missing a requested category → error."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        actual = t["price_rub"] + c["price_rub"]
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], actual)  # no lamp
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair", "lamp"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("expected categories" in e for e in errors)

    def test_extra_category(self, listing_map):
        """Option with category not requested → error."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        l = listing_map[LAMP_ID]
        actual = t["price_rub"] + c["price_rub"] + l["price_rub"]
        response = _valid_ok_response([TABLE_ID, CHAIR_ID, LAMP_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair"],  # no lamp requested
        }
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("expected categories" in e for e in errors)

    def test_duplicate_category_in_option(self, listing_map):
        """Two tables in same option → duplicate category error."""
        # demo-1-1-07 and demo-1-1-08 are both tables
        t1 = TABLE_ID
        t2 = "demo-1-1-08"
        t1_data = listing_map[t1]
        t2_data = listing_map[t2]
        actual = t1_data["price_rub"] + t2_data["price_rub"] + listing_map[CHAIR_ID]["price_rub"]
        response = _valid_ok_response([t1, t2, CHAIR_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("multiple listings of category" in e for e in errors)

    def test_table_category_from_listing(self, listing_map):
        """Categories are inferred from actual listing data."""
        t = listing_map[TABLE_ID]
        assert t["category"] == "table"


# ── Option validation: total_rub ─────────────────────────────────

class TestOptionTotalRub:
    """Validate total_rub calculation."""

    def test_total_rub_correct(self, listing_map):
        """total_rub matches actual sum → no error."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        actual = t["price_rub"] + c["price_rub"]
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        rub_errors = [e for e in errors if "total_rub" in e and "exceeds" not in e]
        assert rub_errors == []

    def test_total_rub_incorrect(self, listing_map):
        """total_rub doesn't match actual sum → error."""
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], 99999)
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("total_rub" in e and "!=" in e for e in errors)

    def test_total_rub_zero(self, listing_map):
        """Zero total_rub with non-zero listings → error."""
        response = _valid_ok_response([TABLE_ID], 0)
        req = {"city_id": "taganrog", "budget_rub": 20000, "categories": ["table"]}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("total_rub" in e for e in errors)


# ── Option validation: budget ────────────────────────────────────

class TestOptionBudget:
    """Validate budget constraint."""

    def test_within_budget(self, listing_map):
        """Total within budget → no budget error."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        actual = t["price_rub"] + c["price_rub"]
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": actual + 1000,  # enough
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        budget_errors = [e for e in errors if "exceeds budget" in e]
        assert budget_errors == []

    def test_exact_budget(self, listing_map):
        """Total equals budget exactly → no budget error."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        actual = t["price_rub"] + c["price_rub"]
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": actual,  # exact
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        budget_errors = [e for e in errors if "exceeds budget" in e]
        assert budget_errors == []

    def test_exceeds_budget(self, listing_map):
        """Total exceeds budget → error."""
        t = listing_map[TABLE_ID]
        c = listing_map[CHAIR_ID]
        actual = t["price_rub"] * 3 + c["price_rub"] * 2
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], actual)
        req = {
            "city_id": "taganrog",
            "budget_rub": 5000,  # low budget
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("exceeds budget" in e for e in errors)

    def test_no_budget_constraint(self, listing_map):
        """When budget is None → no budget error regardless of total."""
        response = _valid_ok_response([TABLE_ID, CHAIR_ID], 999999)
        req = {
            "city_id": "taganrog",
            "budget_rub": None,
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        budget_errors = [e for e in errors if "exceeds budget" in e]
        assert budget_errors == []


# ── Option validation: explanation ───────────────────────────────

class TestOptionExplanation:
    """Validate explanation field."""

    def test_non_empty_explanation(self, listing_map):
        """Non-empty explanation → no error."""
        t = listing_map[TABLE_ID]
        response = _valid_ok_response([TABLE_ID], t["price_rub"], explanation="Стол 60 см, подходит.")
        req = {"city_id": "taganrog", "budget_rub": 10000, "categories": ["table"]}
        errors = validate_response(response, listing_map.values(), req, req)
        exp_errors = [e for e in errors if "explanation" in e]
        assert exp_errors == []

    def test_empty_explanation(self, listing_map):
        """Empty explanation → error."""
        t = listing_map[TABLE_ID]
        response = _valid_ok_response([TABLE_ID], 0, explanation="")
        req = {"city_id": "taganrog", "budget_rub": 10000, "categories": ["table"]}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("explanation must be non-empty" in e for e in errors)

    def test_missing_explanation(self, listing_map):
        """Missing explanation key → error."""
        option = {"listing_ids": [TABLE_ID], "total_rub": 5000}
        response = {"status": "ok", "options": [option]}
        req = {"city_id": "taganrog", "budget_rub": 10000, "categories": ["table"]}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("explanation" in e for e in errors)


# ── Multiple options ──────────────────────────────────────────────

class TestMultipleOptions:
    """Validate responses with multiple options."""

    def test_multiple_valid_options(self, listing_map):
        """Multiple options validated independently."""
        t1 = listing_map[TABLE_ID]
        c1 = listing_map[CHAIR_ID]
        t2 = listing_map["demo-1-1-08"]
        c2 = listing_map["demo-1-2-09"]
        actual1 = t1["price_rub"] + c1["price_rub"]
        actual2 = t2["price_rub"] + c2["price_rub"]
        response = {
            "status": "ok",
            "options": [
                {"listing_ids": [TABLE_ID, CHAIR_ID], "total_rub": actual1, "explanation": "A"},
                {"listing_ids": ["demo-1-1-08", "demo-1-2-09"], "total_rub": actual2, "explanation": "B"},
            ],
        }
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        # Both options should pass
        assert len(errors) == 0

    def test_one_bad_option_detected(self, listing_map):
        """If one option fails, only that option's errors reported."""
        t = listing_map[TABLE_ID]
        response = {
            "status": "ok",
            "options": [
                {"listing_ids": [TABLE_ID], "total_rub": t["price_rub"], "explanation": "Good"},
                {"listing_ids": [], "total_rub": 0, "explanation": ""},  # bad
            ],
        }
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table"],
        }
        errors = validate_response(response, listing_map.values(), req, req)
        # Should detect empty listing_ids and empty explanation on option 1
        assert any("option[1]" in e for e in errors)


# ── Edge cases ───────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_response(self):
        """Completely empty dict → error."""
        errors = validate_response({}, [], {}, {})
        assert any("Unknown status" in e for e in errors)

    def test_none_response(self):
        """None response → graceful error."""
        errors = validate_response(None, [], {}, {})
        assert len(errors) > 0

    def test_no_requirements(self, listing_map):
        """Empty requirements dict → no category errors for ok status."""
        response = _valid_ok_response([TABLE_ID], 5000)
        req = {}
        errors = validate_response(response, listing_map.values(), req, req)
        # No categories expected, none found → mismatch
        assert any("expected categories" in e for e in errors)

    def test_requirements_without_categories(self, listing_map):
        """Requirements without categories key → empty expected set."""
        response = _valid_ok_response([TABLE_ID], 5000)
        req = {"city_id": "taganrog", "budget_rub": 10000}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("expected categories" in e for e in errors)

    def test_listing_with_missing_category(self):
        """Listing without category → category becomes None in check."""
        listing = {"id": "fake", "price_rub": 500}  # no category
        response = _valid_ok_response(["fake"], 500)
        req = {
            "city_id": "taganrog",
            "budget_rub": 10000,
            "categories": ["table"],
        }
        errors = validate_response(response, [listing], req, req)
        # The listing has no category, so categories_found != expected
        cat_errors = [e for e in errors if "categories" in e]
        assert len(cat_errors) > 0

    def test_total_rub_with_nonexistent_ids(self):
        """total_rub calculation should handle non-existent IDs gracefully."""
        response = _valid_ok_response(["nonexistent"], 1000)
        req = {"city_id": "taganrog", "budget_rub": 10000, "categories": ["table"]}
        errors = validate_response(response, [], req, req)
        assert any("not in catalog" in e for e in errors)


# ── Integration-style with real catalog ──────────────────────────

class TestIntegrationWithRealCatalog:
    """Tests using actual catalog data for realistic scenarios."""

    def test_real_ok_response(self, catalog, listing_map):
        """Build a response from real catalog data → valid."""
        t = listing_map["demo-1-1-07"]
        c = listing_map["demo-1-2-03"]
        l = listing_map["demo-1-3-03"]
        actual_total = t["price_rub"] + c["price_rub"] + l["price_rub"]
        response = _valid_ok_response(["demo-1-1-07", "demo-1-2-03", "demo-1-3-03"], actual_total)
        req = {
            "city_id": "taganrog",
            "budget_rub": 20000,
            "categories": ["table", "chair", "lamp"],
        }
        errors = validate_response(response, catalog, req, req)
        assert errors == []

    def test_real_clarify_missing_fields(self, catalog):
        """Clarify asking for missing city and categories → valid."""
        response = _valid_clarify_response([
            {"field": "city_id", "text": "В каком городе вы находитесь?"},
            {"field": "categories", "text": "Какие категории вас интересуют?"},
        ])
        errors = validate_response(response, catalog, {}, {"budget_rub": 10000})
        assert errors == []

    def test_multiple_bad_options(self, listing_map):
        """Multiple options all with errors → all errors reported."""
        response = {
            "status": "ok",
            "options": [
                {"listing_ids": ["fake1"], "total_rub": 0, "explanation": ""},
                {"listing_ids": ["fake2", "fake2"], "total_rub": 999, "explanation": ""},
            ],
        }
        req = {"city_id": "taganrog", "budget_rub": 10000, "categories": ["table"]}
        errors = validate_response(response, listing_map.values(), req, req)
        assert any("fake1" in e for e in errors)
        assert any("fake2" in e for e in errors)
        assert any("duplicate" in e for e in errors)


@pytest.mark.parametrize("response", [
    {"status": "ok", "options": []},
    {"status": "ok", "options": [None]},
    {"status": "ok", "options": [{}] * 4},
    {"status": "ok", "options": [{"listing_ids": ["x"], "total_rub": True, "explanation": "x"}]},
    _valid_ok_response([{}], 1),
    _valid_ok_response(["a", "b", "c", "d"], 4),
    {"status": "clarify", "questions": [{"field": "other", "text": "?"}]},
    {"status": "clarify", "questions": [{"field": "city_id", "text": "?", "id": "a"}]},
    {"status": "clarify", "questions": [{"field": "city_id", "text": "?"}] * 2},
    {"status": "no_match", "message": 1},
    {"status": "no_match", "message": "Нет комплекта", "listing_ids": []},
])
def test_rejects_invalid_response_shape(response):
    assert validate_response_shape(response)


def test_distinct_kit_compositions_ignore_item_order():
    result = _valid_ok_response(["a", "b"], 2)
    result["options"].append(dict(result["options"][0], listing_ids=["b", "a"]))
    assert any("duplicate kit" in error for error in validate_response_shape(result))


@pytest.mark.parametrize(("category", "key", "constraint", "value", "valid"), [
    ("table", "width_cm", {"max": 100}, 100, True),
    ("table", "width_cm", {"max": 100}, 101, False),
    ("lamp", "color_temperature_k", {"min": 4000}, 3999, False),
    ("chair", "adjustable_height", False, False, True),
    ("chair", "adjustable_height", False, True, False),
    ("chair", "adjustable_height", True, True, True),
    ("chair", "adjustable_height", True, False, False),
    ("chair", "adjustable_height", False, None, False),
])
def test_validates_flat_parser_constraints(category, key, constraint, value, valid):
    attributes = {} if value is None else {key: value}
    listing = dict(id="x", city_id="azov", category=category, price_rub=10, attributes=attributes)
    req = dict(city_id="azov", categories=[category], budget_rub=10, constraints={key: constraint})
    ok = _valid_ok_response(["x"], 10)
    assert (validate_response(ok, [listing], {}, req) == []) is valid
    assert bool(validate_response(_valid_no_match_response(), [listing], {}, req)) is valid


def test_clarify_needs_all_missing_fields_including_mixed_categories():
    req = dict(city_id="azov", categories=["table"], budget_rub=None, _has_unsupported_categories=True)
    response = _valid_clarify_response([{"field": "budget_rub", "text": "Бюджет?"}])
    assert validate_response(response, [], {}, req)
    response["questions"].append({"field": "categories", "text": "Какие товары нужны?"})
    assert validate_response(response, [], {}, req) == []
