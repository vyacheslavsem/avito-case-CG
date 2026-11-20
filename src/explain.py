"""Generate explanation text for selected options.

Template-based fallback using catalog data:
- Lists each item with category name, title, and key attributes
- Shows total price and city
- Optionally mentions budget remaining
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Russian category names for display
CATEGORY_NAMES = {
    "table": "Стол",
    "chair": "Кресло",
    "lamp": "Лампа",
}


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
        Explanation string referencing catalog data.
    """
    parts = []

    for l in listings:
        cat = l.get("category", "?")
        title = l.get("title", "?")
        name = CATEGORY_NAMES.get(cat, cat)

        # Build attribute info based on category
        attrs = l.get("attributes", {})
        attr_parts = []

        if cat == "table":
            width = attrs.get("width_cm")
            if width is not None:
                attr_parts.append(f"ширина {width} см")
        elif cat == "chair":
            adj = attrs.get("adjustable_height")
            if adj is not None:
                if adj:
                    attr_parts.append("с регулировкой высоты")
                else:
                    attr_parts.append("без регулировки высоты")
        elif cat == "lamp":
            temp = attrs.get("color_temperature_k")
            if temp is not None:
                attr_parts.append(f"{temp} К")

        # Assemble item string
        if attr_parts:
            parts.append(f"{name} '{title}', " + ", ".join(attr_parts))
        else:
            parts.append(f"{name} '{title}'")

    # City info
    city_names = {"taganrog": "Таганрог", "rostov-na-donu": "Ростов-на-Дону", "azov": "Азов"}
    city_name = city_names.get(city_id, city_id)
    parts.append(f"Все товары в {city_name}")

    # Price info
    parts.append(f"Итого: {total_rub} руб.")

    if budget is not None:
        remaining = budget - total_rub
        parts.append(f"Остаток бюджета: {remaining} руб.")

    return ". ".join(parts) + "."
