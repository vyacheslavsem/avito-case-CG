"""Build kit combinations from filtered listings.

Algorithm:
  1. For each requested category, get filtered listings.
  2. Use itertools.product to enumerate one-per-category combos.
  3. Filter combos where sum(price_rub) ≤ budget.
  4. Rank by total price (cheapest first) and return up to 3.
"""
import itertools
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
            "explanation": str
        }
        
    Raises:
        ValueError: If any category has zero listings (caller should return no_match).
    """
    if not category_listings:
        logger.warning("No categories provided for combination building")
        return []

    # Check that each category has at least one listing
    for category, listings in category_listings.items():
        if not listings:
            logger.warning("Category '%s' has no listings", category)
            raise ValueError(f"No listings available for category: {category}")

    categories = list(category_listings.keys())
    listings_per_category = [category_listings[cat] for cat in categories]

    # Enumerate all possible combinations (one item per category)
    all_combos = itertools.product(*listings_per_category)

    valid_combos = []
    for combo in all_combos:
        total_price = sum(item["price_rub"] for item in combo)

        # Filter by budget if specified
        if budget is not None and total_price > budget:
            continue

        listing_ids = [item["id"] for item in combo]
        explanation = _generate_explanation(combo, categories)

        valid_combos.append({
            "listing_ids": listing_ids,
            "total_rub": total_price,
            "explanation": explanation,
        })

    # Rank by total price (cheapest first)
    valid_combos.sort(key=lambda x: x["total_rub"])

    # Return up to max_options
    return valid_combos[:max_options]


def _generate_explanation(combo: tuple[dict, ...], categories: list[str]) -> str:
    """Generate a human-readable explanation for the kit combination.

    Args:
        combo: tuple of listing dicts (one per category).
        categories: list of category names in order.

    Returns:
        Explanation string in Russian describing the selection.
    """
    parts = []
    for listing, category in zip(combo, categories):
        title = listing.get("title", "")
        price = listing["price_rub"]
        attrs = listing.get("attributes", {})

        if category == "table" and "width_cm" in attrs:
            parts.append(f"Стол '{title}' ({attrs['width_cm']} см, {price} руб.)")
        elif category == "chair" and "adjustable_height" in attrs:
            adj = "с регулировкой высоты" if attrs["adjustable_height"] else "без регулировки высоты"
            parts.append(f"Кресло '{title}' ({adj}, {price} руб.)")
        elif category == "lamp" and "color_temperature_k" in attrs:
            parts.append(f"Лампа '{title}' ({attrs['color_temperature_k']} К, {price} руб.)")
        else:
            parts.append(f"{title} ({price} руб.)")

    return "Комплект: " + ", ".join(parts) + "."
