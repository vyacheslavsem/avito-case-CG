"""Load and filter product catalog.

Supported categories and attributes:
  table   → width_cm        (int, supports ≤, ≥, =, ranges)
  chair   → adjustable_height (bool, true / false)
  lamp    → color_temperature_k (int, supports ≤, ≥, =, ranges)
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def load_catalog(path: str) -> list[dict]:
    """Load catalog JSON file and return list of listing dicts."""
    # TODO: read file, validate schema
    logger.info("catalog.py: placeholder — not yet implemented")
    return []


def filter_by_city(listings: list[dict], city_id: str) -> list[dict]:
    """Filter listings to only those in the buyer's city."""
    return [l for l in listings if l.get("city_id") == city_id]


def filter_by_category(listings: list[dict], category: str) -> list[dict]:
    """Filter listings to only those in the requested category."""
    return [l for l in listings if l.get("category") == category]


def matches_attribute(listing: dict, category: str, constraint: dict) -> bool:
    """Check if a listing satisfies the attribute constraint.

    constraint shape: {"min": int | None, "max": int | None} for numeric,
    or {"value": bool} for boolean.

    Returns False if attribute is missing (unknown = no match).
    """
    # TODO: implement attribute matching logic
    # TODO: handle ≤, ≥, =, <, > boundary rules
    logger.info("catalog.py matches_attribute: placeholder")
    return False


def filter_by_attributes(listings: list[dict], category: str, constraints: dict) -> list[dict]:
    """Filter listings by all attribute constraints for a category."""
    # TODO: implement
    return listings
