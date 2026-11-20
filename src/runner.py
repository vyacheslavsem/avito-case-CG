"""Process one buyer dialog using the catalog supplied on the command line."""
import argparse
import json
import logging
from pathlib import Path
import sys

from . import catalog, combinator, explain, parser, validator


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("invalid JSON number")


def read_request(raw: bytes) -> dict:
    request = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys,
                         parse_constant=reject_constant)
    if not isinstance(request, dict) or set(request) != {"messages"}:
        raise ValueError("expected an object containing only messages")
    messages = request["messages"]
    if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        raise ValueError("expected 1 to 20 messages")
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or set(message) != {"role", "text"}:
            raise ValueError("each message must contain role and text")
        expected_role = "user" if index % 2 == 0 else "assistant"
        if message["role"] != expected_role:
            raise ValueError("roles must alternate starting with user")
        if not isinstance(message["text"], str) or not message["text"]:
            raise ValueError("message text must be a non-empty string")
    if messages[-1]["role"] != "user":
        raise ValueError("the last message must come from the buyer")
    return request


def select_response(listings: list[dict], requirements: dict) -> dict:
    questions = parser.needs_clarify(requirements)
    if questions:
        return {"status": "clarify", "questions": questions}

    city = requirements["city_id"]
    budget = requirements["budget_rub"]
    local = catalog.filter_by_city(listings, city)
    candidates = {}
    for category in requirements["categories"]:
        items = catalog.filter_by_category(local, category)
        candidates[category] = catalog.filter_by_attributes(
            items, category, requirements.get("constraints") or {}
        )
    if not all(candidates.values()):
        return {"status": "no_match", "message": (
            "В выбранном городе нет всех нужных товаров с указанными характеристиками. "
            "Попробуйте изменить город или требования к товарам."
        )}

    options = combinator.build_combinations(candidates, budget)
    if not options:
        return {"status": "no_match", "message": (
            "Полный комплект не укладывается в бюджет. "
            "Попробуйте увеличить бюджет или изменить состав комплекта."
        )}
    by_id = {item["id"]: item for item in listings}
    for option in options:
        selected = [by_id[item_id] for item_id in option["listing_ids"]]
        option["explanation"] = explain.generate_explanation(selected, city, option["total_rub"], budget)
    return {"status": "ok", "options": options}


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--catalog", required=True, type=Path)
    args = cli.parse_args()
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
    stage = "read request"
    try:
        request = read_request(sys.stdin.buffer.read())
        stage = "load catalog"
        if not args.catalog.is_file():
            raise FileNotFoundError("catalog file not found")
        listings = catalog.load_catalog(str(args.catalog))
        stage = "parse buyer dialog"
        requirements = parser.parse_request(request["messages"])
        stage = "select response"
        response = select_response(listings, requirements)
        stage = "validate response"
        if validator.validate_response(response, listings, request, requirements):
            raise ValueError("invalid pipeline response")
        stage = "write response"
        payload = json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8")
        sys.stdout.buffer.write(payload + b"\n")
        sys.stdout.buffer.flush()
    except Exception as error:
        # Dependencies can include credentials or dialog text in exception messages.
        detail = str(error) if stage == "read request" and isinstance(error, ValueError) else type(error).__name__
        logging.error("Cannot %s: %s", stage, detail)
        return 1
    return 0
