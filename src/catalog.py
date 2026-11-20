"""Load and filter product catalog.

Supported categories and attributes:
  table   → width_cm        (int, supports ≤, ≥, =, ranges)
  chair   → adjustable_height (bool, true / false)
  lamp    → color_temperature_k (int, supports ≤, ≥, =, ranges)

Boundary rules (from CONTRACT.md):
  - "до", "не более", "не шире", "от", "не менее" → include boundary (≤, ≥)
  - "меньше", "больше", "уже", "шире" → strict boundary (<, >)
  - "от X до Y" → inclusive range [X, Y]
  - Missing attribute → unknown → does NOT match
"""
import json
import logging

logger = logging.getLogger(__name__)


def load_catalog(path: str) -> list[dict]:
    """Load catalog JSON file and return list of listing dicts."""
    with open(path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    logger.info(f"Loaded {len(catalog)} listings from {path}")
    return catalog


def filter_by_city(listings: list[dict], city_id: str) -> list[dict]:
    """Filter listings to only those in the buyer's city."""
    return [l for l in listings if l.get("city_id") == city_id]


def filter_by_category(listings: list[dict], category: str) -> list[dict]:
    """Filter listings to only those in the requested category."""
    return [l for l in listings if l.get("category") == category]


def _check_numeric_constraint(value: int, constraint: dict) -> bool:
    """Check if a numeric value satisfies the constraint.

    Args:
        value: the listing's attribute value (e.g. width_cm).
        constraint: {"min": int | None, "max": int | None}

    Returns:
        True if the value satisfies all specified bounds.
        Returns False if constraint is missing or None.
    """
    if not isinstance(constraint, dict):
        return False

    if "min" in constraint and constraint["min"] is not None:
        if value < constraint["min"]:
            return False

    if "max" in constraint and constraint["max"] is not None:
        if value > constraint["max"]:
            return False

    return True


def _check_boolean_constraint(value: bool, constraint) -> bool:
    """Check if a boolean value satisfies the constraint.

    Args:
        value: the listing's attribute value (e.g. adjustable_height).
        constraint: True (must be true), False (must be false), or {"value": bool}

    Returns:
        True if the value matches.
        Returns False if constraint is missing or None.
    """
    if constraint is True:
        return value is True
    elif constraint is False:
        return value is False
    elif isinstance(constraint, dict) and "value" in constraint:
        return value == constraint["value"]
    return False


def matches_attribute(listing: dict, category: str, constraint: dict) -> bool:
    """Check if a listing satisfies the attribute constraint.

    Args:
        listing: a listing dict with "attributes" field.
        category: the listing's category (table, chair, lamp).
        constraint: attribute constraint dict or {"value": bool}.

    Returns:
        True if the listing matches.
        Returns False if attribute is missing (unknown = no match).
    """
    attrs = listing.get("attributes", {})

    if category == "table":
        value = attrs.get("width_cm")
        if value is None:
            return False
        return _check_numeric_constraint(value, constraint)

    elif category == "chair":
        value = attrs.get("adjustable_height")
        if value is None:
            return False
        return _check_boolean_constraint(value, constraint)

    elif category == "lamp":
        value = attrs.get("color_temperature_k")
        if value is None:
            return False
        return _check_numeric_constraint(value, constraint)

    return False


def filter_by_attributes(listings: list[dict], category: str, constraints: dict) -> list[dict]:
    """Filter listings by all attribute constraints for a category.

    Args:
        listings: listings already filtered by city and category.
        category: the category to filter on (table, chair, lamp).
        constraints: dict of constraint key → constraint value.
                     E.g. {"width_cm": {"min": None, "max": 100}}

    Returns:
        Filtered list of listings that satisfy ALL constraints.
    """
    if not constraints:
        return list(listings)

    result = []
    for listing in listings:
        attrs = listing.get("attributes", {})
        matches = True

        for key, constraint in constraints.items():
            value = attrs.get(key)

            # Missing attribute → unknown → no match
            if value is None:
                matches = False
                break

            # Apply constraint based on type
            if isinstance(constraint, dict) and key in ("width_cm", "color_temperature_k"):
                # Numeric constraint: {"min": int, "max": int}
                if not _check_numeric_constraint(value, constraint):
                    matches = False
                    break
            elif isinstance(constraint, dict) and "value" in constraint:
                # Boolean constraint via dict: {"value": True/False}
                if value != constraint["value"]:
                    matches = False
                    break
            elif isinstance(constraint, bool):
                # Boolean constraint directly: True or False
                if value != constraint:
                    matches = False
                    break

        if matches:
            result.append(listing)

    return result
