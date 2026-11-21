"""Validate the wire response and its consistency with the parsed buyer requirements."""
if __package__:
    from .catalog import matches_attribute
else:  # The Linux launcher also supports running src/runner.py as a script.
    from catalog import matches_attribute


CATEGORY_ATTRIBUTES = {
    "table": "width_cm",
    "chair": "adjustable_height",
    "lamp": "color_temperature_k",
}
QUESTION_FIELDS = {"budget_rub", "city_id", "categories"}


def _nonempty_text(value):
    return isinstance(value, str) and bool(value)


def _option_shape(option, idx, kits):
    prefix = f"option[{idx}]"
    if not isinstance(option, dict):
        return [f"{prefix} must be an object"]
    errors = []
    if set(option) != {"listing_ids", "total_rub", "explanation"}:
        errors.append(f"{prefix} must contain only listing_ids, total_rub and explanation")
    ids = option.get("listing_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 3:
        errors.append(f"{prefix}: listing_ids must not be empty and must contain 1–3 IDs")
    elif not all(_nonempty_text(item) for item in ids):
        errors.append(f"{prefix}: listing_ids must contain non-empty strings")
    else:
        kit = frozenset(ids)
        if len(kit) != len(ids):
            errors.append(f"{prefix}: duplicate listing_ids")
        if kit in kits:
            errors.append(f"{prefix}: duplicate kit")
        kits.add(kit)
    if type(option.get("total_rub")) is not int or option["total_rub"] < 1:
        errors.append(f"{prefix}: total_rub must be a positive integer")
    if not _nonempty_text(option.get("explanation")):
        errors.append(f"{prefix}: explanation must be non-empty text")
    return errors


def validate_response_shape(response: dict) -> list[str]:
    """Check response fields, types, cardinalities and uniqueness without a catalog."""
    if not isinstance(response, dict):
        return ["Response must be a dict"]
    status = response.get("status")
    if status not in ("ok", "clarify", "no_match"):
        return [f"Unknown status: {status!r}"]
    field = {"ok": "options", "clarify": "questions", "no_match": "message"}[status]
    errors = []
    if set(response) != {"status", field}:
        errors.append(f"{status} must contain only status and {field}")
    value = response.get(field)
    if status == "ok":
        if not isinstance(value, list) or not 1 <= len(value) <= 3:
            errors.append("ok must have 1–3 options")
        else:
            kits = set()
            for idx, option in enumerate(value):
                errors.extend(_option_shape(option, idx, kits))
    elif status == "clarify":
        if not isinstance(value, list) or not 1 <= len(value) <= 3:
            errors.append("clarify must have a non-empty questions array of up to 3 items")
        else:
            seen = set()
            for question in value:
                if not isinstance(question, dict) or set(question) != {"field", "text"}:
                    errors.append("each question must contain exactly field and text")
                    continue
                name = question["field"]
                if not isinstance(name, str) or name not in QUESTION_FIELDS or name in seen:
                    errors.append("each question must name a distinct main condition")
                else:
                    seen.add(name)
                if not _nonempty_text(question["text"]):
                    errors.append("question text must be a non-empty string")
    elif not _nonempty_text(value):
        errors.append("no_match must have a non-empty message")
    return errors


def _matches(listing, constraints):
    attr = CATEGORY_ATTRIBUTES.get(listing.get("category"))
    condition = constraints.get(attr)
    return condition is None or matches_attribute(listing, listing["category"], condition)


def _validate_selection(option, idx, listings, requirements):
    """Report independent catalog/price errors even when another option field is invalid."""
    if not isinstance(option, dict):
        return []
    ids = option.get("listing_ids")
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        return []
    prefix = f"option[{idx}]"
    errors = []
    categories = set()
    total = 0
    constraints = requirements.get("constraints") or {}
    for item_id in ids:
        listing = listings.get(item_id)
        if listing is None:
            errors.append(f"{prefix}: listing_id {item_id!r} not in catalog")
            continue
        category = listing.get("category")
        if category in categories:
            errors.append(f"{prefix}: multiple listings of category {category!r}")
        categories.add(category)
        if listing.get("city_id") != requirements.get("city_id"):
            errors.append(f"{prefix}: listing {item_id!r} is in {listing.get('city_id')}, "
                          f"not in {requirements.get('city_id')}")
        if not _matches(listing, constraints):
            errors.append(f"{prefix}: listing {item_id!r} does not satisfy constraints")
        total += listing["price_rub"]
    expected = set(requirements.get("categories") or [])
    if categories != expected:
        errors.append(f"{prefix}: expected categories {expected}, got {categories}")
    reported = option.get("total_rub")
    if reported != total:
        errors.append(f"{prefix}: total_rub {reported!r} != actual sum {total}")
    budget = requirements.get("budget_rub")
    if type(reported) is int and budget is not None and reported > budget:
        errors.append(f"{prefix}: total_rub {reported} exceeds budget {budget}")
    return errors


def _kit_exists(catalog, requirements):
    # With one listing per distinct category, the cheapest in each makes the cheapest kit.
    expected = set(requirements["categories"])
    constraints = requirements.get("constraints") or {}
    cheapest = {}
    for listing in catalog:
        category = listing["category"]
        if category not in expected or listing["city_id"] != requirements["city_id"]:
            continue
        if _matches(listing, constraints):
            price = listing["price_rub"]
            cheapest[category] = min(price, cheapest.get(category, price))
    return expected == cheapest.keys() and sum(cheapest.values()) <= requirements["budget_rub"]


def validate_response(response: dict, catalog: list[dict], request: dict, requirements: dict) -> list[str]:
    """Check an answer using the catalog and the intent parsed from the full request."""
    errors = validate_response_shape(response)
    if not isinstance(response, dict):
        return errors
    missing = set()
    if not requirements.get("city_id"):
        missing.add("city_id")
    if not requirements.get("categories") or requirements.get("_has_unsupported_categories"):
        missing.add("categories")
    if requirements.get("budget_rub") is None:
        missing.add("budget_rub")

    status = response.get("status")
    if status == "clarify" and not errors:
        if {question["field"] for question in response["questions"]} != missing:
            errors.append(f"clarify must ask exactly about missing fields: {sorted(missing)}")
    elif status in ("ok", "no_match"):
        if missing:
            errors.append(f"expected clarify for missing fields: {sorted(missing)}")
        if status == "ok" and isinstance(response.get("options"), list):
            listings = {row["id"]: row for row in catalog if isinstance(row, dict) and "id" in row}
            for idx, option in enumerate(response["options"]):
                errors.extend(_validate_selection(option, idx, listings, requirements))
        elif status == "no_match" and not errors and _kit_exists(catalog, requirements):
            errors.append("no_match despite a complete affordable kit in the catalog")
    return errors
