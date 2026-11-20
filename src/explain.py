"""Generate explanation text for selected options.

Fallback: template-based explanation using catalog data.
Optional: LLM-generated explanation for richer text.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_explanation(
    listings: list[dict],
    city_id: str,
    total_rub: int,
    budget: Optional[int] = None,
) -> str:
    """Generate a human-readable explanation for an option.

    Args:
        listings: the listings in this option.
        city_id: buyer's city.
        total_rub: total price.
        budget: optional budget for context.

    Returns:
        Explanation string.
    """
    # TODO: implement template-based fallback
    # Example: "Стол {title}, {width} см, кресло {title}, {adj}, лампа {title}, {temp} К. "
    #          "Все товары в городе {city}. Итого: {total} руб."
    logger.info("explain.py: placeholder — not yet implemented")
    parts = []
    for l in listings:
        cat = l.get("category", "?")
        title = l.get("title", "?")
        parts.append(f"{cat}: {title}")
    return ", ".join(parts) + f". Итого: {total_rub} руб."
