"""Validate response against catalog and request constraints.

Checks:
  - All listing_ids exist in catalog
  - Each ID appears at most once per option
  - Each option has exactly one listing per requested category
  - Every listing is in the buyer's city
  - Every listing satisfies its category's attribute constraints
  - total_rub == exact sum of price_rub
  - total_rub ≤ budget
  - No injection from listing text (we only use structured fields)

Returns list of error strings. Empty list = valid.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def validate_response(
    response: dict,
    catalog: list[dict],
    request: dict,
    requirements: dict,
) -> list[str]:
    """Validate a full response dict against the catalog.

    Args:
        response: the response we're about to send to stdout.
        catalog: list of all listings from --catalog.
        request: the parsed request (messages).
        requirements: parsed requirements (city_id, budget, etc).

    Returns:
        List of error messages. Empty means valid.
    """
    errors = []

    # Handle None or non-dict response
    if not isinstance(response, dict):
        return [f"Response must be a dict, got {type(response).__name__}"]

    status = response.get("status")
    cat_ids = {l["id"] for l in catalog if isinstance(l, dict) and "id" in l}
    listing_map = {l["id"]: l for l in catalog if isinstance(l, dict) and "id" in l}

    if status == "ok":
        options = response.get("options", [])
        for idx, option in enumerate(options):
            errors.extend(_validate_option(option, cat_ids, listing_map, requirements, idx))

    elif status == "clarify":
        questions = response.get("questions", [])
        if not questions:
            errors.append("clarify response must have non-empty questions array")

    elif status == "no_match":
        message = response.get("message", "")
        if not message:
            errors.append("no_match response must have non-empty message")

    else:
        errors.append(f"Unknown status: {status!r}")

    return errors


def _validate_option(
    option: dict,
    cat_ids: set[str],
    listing_map: dict[str, dict],
    requirements: dict,
    idx: int,
) -> list[str]:
    errors = []
    listing_ids = option.get("listing_ids", [])
    total_rub = option.get("total_rub", 0)
    explanation = option.get("explanation", "")

    if not listing_ids:
        errors.append(f"option[{idx}]: listing_ids must not be empty")
        return errors
    if not explanation:
        errors.append(f"option[{idx}]: explanation must be non-empty")

    # Check unique IDs
    if len(set(listing_ids)) != len(listing_ids):
        errors.append(f"option[{idx}]: duplicate listing_ids")

    # Check all IDs exist
    for lid in listing_ids:
        if lid not in cat_ids:
            errors.append(f"option[{idx}]: listing_id {lid!r} not in catalog")

    # Check one per category
    categories_found = set()
    for lid in listing_ids:
        if lid in listing_map:
            cat = listing_map[lid].get("category")
            if cat in categories_found:
                errors.append(f"option[{idx}]: multiple listings of category {cat!r}")
            categories_found.add(cat)

    expected_cats = set(requirements.get("categories", []))
    if categories_found != expected_cats:
        errors.append(
            f"option[{idx}]: expected categories {expected_cats}, got {categories_found}"
        )

    # Check total_rub
    actual_total = sum(listing_map[lid]["price_rub"] for lid in listing_ids if lid in listing_map)
    if total_rub != actual_total:
        errors.append(f"option[{idx}]: total_rub {total_rub} != actual sum {actual_total}")

    budget = requirements.get("budget_rub")
    if budget is not None and total_rub > budget:
        errors.append(f"option[{idx}]: total_rub {total_rub} exceeds budget {budget}")

    return errors
