#!/usr/bin/env python3
"""Entry point for the AI Buyer Assistant.

Pipeline:
  1. Parse --catalog from argv
  2. Read request JSON from stdin
  3. Load catalog
  4. Parse dialog → requirements (LLM)
  5. Filter catalog by requirements
  6. Build combinations
  7. Validate response
  8. Write JSON to stdout

Usage:
    ./run --catalog /path/to/catalog.json < request.json > response.json
"""
import sys
import os
import json
import argparse
import logging

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def unique_keys(pairs):
    """Detect duplicate keys in JSON objects."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def reject_constant(value):
    """Reject JSON NaN/Infinity/Infinity."""
    raise ValueError("invalid JSON number (NaN/Infinity)")


def read_request(raw: bytes) -> dict:
    """Parse and validate request from stdin bytes.

    Validates:
    - Single top-level object with only 'messages' key
    - 1-20 messages
    - Alternating roles (user, assistant, user, ...)
    - Each message has exactly {role, text}
    - Last message is from user
    - No NaN/Infinity/duplicate keys
    """
    request = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys,
                         parse_constant=reject_constant)
    if not isinstance(request, dict) or set(request) != {"messages"}:
        raise ValueError("expected an object containing only messages")
    messages = request["messages"]
    if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
        raise ValueError("expected 1 to 20 messages")
    for index, message in enumerate(messages):
        if not isinstance(message, dict) or set(message) != {"role", "text"}:
            raise ValueError("each message must contain role and text only")
        expected_role = "user" if index % 2 == 0 else "assistant"
        if message["role"] != expected_role:
            raise ValueError(f"message[{index}] role expected {expected_role!r}, got {message['role']!r}")
        if not isinstance(message["text"], str) or not message["text"]:
            raise ValueError("message text must be a non-empty string")
    if messages[-1]["role"] != "user":
        raise ValueError("the last message must come from the buyer")
    return request


def main() -> int:
    # Parse arguments
    cli = argparse.ArgumentParser(description="AI Buyer Assistant")
    cli.add_argument("--catalog", required=True, help="Path to catalog JSON file")
    args = cli.parse_args()

    try:
        return process_request(args.catalog)
    except Exception as exc:
        logger.error("Request processing failed (%s)", type(exc).__name__)
        return 1


def process_request(catalog_path: str) -> int:
    # Load catalog
    try:
        logger.info(f"Loading catalog from {catalog_path}")
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog_data = json.load(f, object_pairs_hook=unique_keys, parse_constant=reject_constant)
        if not isinstance(catalog_data, list) or any(not isinstance(item, dict) for item in catalog_data):
            raise ValueError("expected an array of catalog entries")
        logger.info(f"Loaded {len(catalog_data)} listings")
    except FileNotFoundError:
        logger.error(f"Catalog not found: {catalog_path}")
        return 1
    except (OSError, ValueError) as e:
        logger.error(f"Cannot read catalog: {e}")
        return 1

    # Read request from stdin with strict validation
    try:
        request = read_request(sys.stdin.buffer.read())
        messages = request["messages"]
        logger.info(f"Processing request with {len(messages)} messages")
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"Invalid request: {e}")
        return 1

    # Keep direct python src/runner.py calls compatible with the root launcher.
    if not __package__:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from src.parser import parse_request, needs_clarify, LLMError
        from src.catalog import filter_by_city, filter_by_category, filter_by_attributes
        from src.combinator import build_combinations
        from src.validator import validate_response
        from src.explain import generate_explanation
    except ImportError as exc:
        logger.error("Cannot load dependency: %s", exc.name)
        return 1

    # Step 1: Parse dialog → requirements
    try:
        requirements = parse_request(messages)
    except LLMError as e:
        # CONTRACT §1: external service errors → stderr + non-zero exit
        logger.error(f"LLM API error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error parsing request: {e}")
        return 1

    # Step 2: Check if we need to clarify
    questions = needs_clarify(requirements)

    if questions:
        response = {
            "status": "clarify",
            "questions": questions,
        }
        logger.info(f"Returning clarify with {len(questions)} questions")
    else:
        # Step 3: Filter catalog by requirements
        city_id = requirements["city_id"]
        categories = requirements["categories"]
        budget = requirements["budget_rub"]
        raw_constraints = requirements.get("constraints", {})

        # Map attribute names to categories for proper filtering
        attr_to_category = {
            "width_cm": "table",
            "adjustable_height": "chair",
            "color_temperature_k": "lamp",
        }
        # Build per-category constraint dicts
        per_cat_constraints = {}
        for attr, cat in attr_to_category.items():
            if attr in raw_constraints and raw_constraints[attr] is not None:
                if cat not in per_cat_constraints:
                    per_cat_constraints[cat] = {}
                per_cat_constraints[cat][attr] = raw_constraints[attr]

        logger.info(f"Filtering: city={city_id}, categories={categories}, budget={budget}")

        # Filter by city
        city_listings = filter_by_city(catalog_data, city_id)
        logger.info(f"After city filter: {len(city_listings)} listings")

        # Group by category and filter
        category_listings = {}
        for cat in categories:
            cat_listings = filter_by_category(city_listings, cat)

            # Apply attribute constraints for this category
            cat_constraints = per_cat_constraints.get(cat)
            if cat_constraints:
                cat_listings = filter_by_attributes(cat_listings, cat, cat_constraints)

            category_listings[cat] = cat_listings
            logger.info(f"Category {cat}: {len(cat_listings)} listings")

        # Step 4: Build combinations
        try:
            options = build_combinations(category_listings, budget, max_options=3)
            logger.info(f"Built {len(options)} options")
        except Exception as e:
            logger.error(f"Error building combinations: {e}")
            return 1

        if not options:
            # No match found
            message = _generate_no_match_message(categories, city_id, budget, category_listings)
            response = {
                "status": "no_match",
                "message": message,
            }
            logger.info(f"Returning no_match: {message}")
        else:
            # Complete each option before validating it.
            response = {
                "status": "ok",
                "options": [],
            }
            for option in options:
                # Get listings for this option
                option_listing_ids = option["listing_ids"]
                option_listings = [l for l in catalog_data if l["id"] in option_listing_ids]

                # Generate explanation
                explanation = generate_explanation(
                    option_listings, city_id, option["total_rub"], budget
                )
                option["explanation"] = explanation

                response["options"].append(option)

    errors = validate_response(response, catalog_data, request, requirements)
    if errors:
        logger.error("Invalid pipeline response: %s", errors)
        return 1

    # Write response to stdout (binary to prevent encoding issues)
    try:
        payload = json.dumps(response, ensure_ascii=False, allow_nan=False).encode("utf-8")
        sys.stdout.buffer.write(payload + b"\n")
        sys.stdout.buffer.flush()
    except Exception as e:
        logger.error(f"Error writing response: {e}")
        return 1

    return 0


def _generate_no_match_message(categories: list, city_id: str, budget: int, category_listings: dict) -> str:
    """Generate a helpful no_match message.
    
    Uses actual budget value from requirements, not hardcoded threshold.
    """
    city_names = {"taganrog": "Таганрог", "rostov-na-donu": "Ростов-на-Дону", "azov": "Азов"}
    city_name = city_names.get(city_id, city_id)
    cat_names = {"table": "стол", "chair": "кресло", "lamp": "лампа"}
    missing = [cat_names[cat] for cat in categories if not category_listings[cat]]
    if missing:
        return (f"По вашим условиям в городе {city_name} отсутствуют: {', '.join(missing)}. "
                "Попробуйте изменить город, состав комплекта или требования к характеристикам.")
    return (f"В городе {city_name} полный комплект стоит больше {budget} руб. "
            "Попробуйте увеличить бюджет или изменить состав комплекта.")


if __name__ == "__main__":
    raise SystemExit(main())
