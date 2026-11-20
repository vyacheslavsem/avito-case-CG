"""Build kit combinations from filtered listings.

Algorithm:
  1. For each requested category, get filtered listings.
  2. Use itertools.product to enumerate one-per-category combos.
  3. Filter combos where sum(price_rub) ≤ budget.
  4. Rank by total price (cheapest first) and return up to 3.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def build_combinations(
    category_listings: dict[str, list[dict]],
    budget: Optional[int],
    max_options: int = 3,
) -> list[dict]:
    """Build kit combinations.

    Args:
        category_listings: {category: [listing, ...]} for each requested category.
        budget: maximum total price (None = no budget limit).
        max_options: return at most this many options.

    Returns:
        List of option dicts: {
            "listing_ids": [id, ...],
            "total_rub": int,
            "explanation": str  # TODO: fill later
        }
    """
    # TODO: implement combination logic
    # TODO: handle case where a category has 0 listings → no_match
    # TODO: handle case where all combos exceed budget → no_match
    logger.info("combinator.py: placeholder — not yet implemented")
    return []
