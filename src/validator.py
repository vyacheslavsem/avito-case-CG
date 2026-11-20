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


def _check_attribute_constraint(
    listing: dict,
    category: str,
    constraint: dict,
) -> bool:
    """Check if a listing satisfies a single attribute constraint.

    Returns True if the listing matches, False otherwise.
    Missing attribute = unknown = does not match.
    """
    attrs = listing.get("attributes", {})

    if category == "table":
        width = attrs.get("width_cm")
        if width is None:
            return False
        if isinstance(constraint, dict):
            if "min" in constraint and constraint["min"] is not None:
                if width < constraint["min"]:
                    return False
            if "max" in constraint and constraint["max"] is not None:
                # "max" means inclusive (до, не шире, не более)
                # "exclusive_max" would mean strict (меньше, уже, не шире)
                if width > constraint["max"]:
                    return False
        return True

    elif category == "chair":
        adj = attrs.get("adjustable_height")
        if adj is None:
            return False
        if isinstance(constraint, dict):
            if "value" in constraint:
                return adj == constraint["value"]
            elif constraint is True:
                return adj is True
            elif constraint is False:
                return adj is False
        return False

    elif category == "lamp":
        temp = attrs.get("color_temperature_k")
        if temp is None:
            return False
        if isinstance(constraint, dict):
            if "min" in constraint and constraint["min"] is not None:
                if temp < constraint["min"]:
                    return False
            if "max" in constraint and constraint["max"] is not None:
                if temp > constraint["max"]:
                    return False
        return True

    return True


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

    # Check city for each listing
    buyer_city = requirements.get("city_id")
    if buyer_city:
        for lid in listing_ids:
            if lid in listing_map:
                listing = listing_map[lid]
                if listing.get("city_id") != buyer_city:
                    errors.append(
                        f"option[{idx}]: listing {lid!r} is in {listing.get('city_id')}, "
                        f"not in {buyer_city}"
                    )

    # Check attribute constraints for each listing
    constraints = requirements.get("constraints", {})
    if constraints:
        for lid in listing_ids:
            if lid in listing_map:
                listing = listing_map[lid]
                cat = listing.get("category")
                cat_constraint = constraints.get(cat)
                if cat_constraint:
                    if not _check_attribute_constraint(listing, cat, cat_constraint):
                        attrs = listing.get("attributes", {})
                        errors.append(
                            f"option[{idx}]: listing {lid!r} ({cat}) "
                            f"does not satisfy constraints: {cat_constraint}"
                        )

    return errors
