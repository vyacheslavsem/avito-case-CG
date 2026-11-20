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


def main() -> int:
    # Parse arguments
    parser = argparse.ArgumentParser(description="AI Buyer Assistant")
    parser.add_argument("--catalog", required=True, help="Path to catalog JSON file")
    args = parser.parse_args()

    catalog_path = args.catalog

    # Load catalog
    try:
        logger.info(f"Loading catalog from {catalog_path}")
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        logger.info(f"Loaded {len(catalog)} listings")
    except FileNotFoundError:
        logger.error(f"Catalog not found: {catalog_path}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid catalog JSON: {e}")
        return 1

    # Read request from stdin
    try:
        raw = sys.stdin.read()
        request = json.loads(raw)
        messages = request.get("messages", [])
        if not messages:
            logger.error("Request has no messages")
            return {"error": "No messages in request"}
        logger.info(f"Processing request with {len(messages)} messages")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid request JSON: {e}")
        return 1

    # Import modules (handle both script and module execution)
    try:
        from src.parser import parse_request, needs_clarify
        from src.catalog import filter_by_city, filter_by_category, filter_by_attributes, matches_attribute
        from src.combinator import build_combinations
        from src.validator import validate_response
        from src.explain import generate_explanation
    except ImportError:
        from parser import parse_request, needs_clarify
        from catalog import filter_by_city, filter_by_category, filter_by_attributes, matches_attribute
        from combinator import build_combinations
        from validator import validate_response
        from explain import generate_explanation

    # Step 1: Parse dialog → requirements
    try:
        requirements = parse_request(messages)
        logger.info(f"Parsed requirements: {requirements}")
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
        constraints = requirements.get("constraints", {})

        logger.info(f"Filtering: city={city_id}, categories={categories}, budget={budget}")

        # Filter by city
        city_listings = filter_by_city(catalog, city_id)
        logger.info(f"After city filter: {len(city_listings)} listings")

        # Group by category and filter
        category_listings = {}
        for cat in categories:
            cat_listings = filter_by_category(city_listings, cat)

            # Apply attribute constraints
            cat_constraints = constraints.get(cat)
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
            # Validate and add explanations
            response = {
                "status": "ok",
                "options": [],
            }
            for option in options:
                # Get listings for this option
                option_listing_ids = option["listing_ids"]
                option_listings = [l for l in catalog if l["id"] in option_listing_ids]

                # Generate explanation
                explanation = generate_explanation(
                    option_listings, city_id, option["total_rub"], budget
                )
                option["explanation"] = explanation

                response["options"].append(option)

            # Validate response
            errors = validate_response(response, catalog, request, requirements)
            if errors:
                logger.error(f"Validation failed: {errors}")
                # If validation fails, return no_match
                message = "К сожалению, не удалось подобрать комплект по заданным условиям. Попробуйте изменить параметры поиска."
                response = {
                    "status": "no_match",
                    "message": message,
                }
            else:
                logger.info(f"Validation passed, returning {len(options)} options")

    # Write response to stdout
    try:
        json.dump(response, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        print()  # trailing newline as allowed by contract
    except Exception as e:
        logger.error(f"Error writing response: {e}")
        return 1

    return 0


def _generate_no_match_message(categories: list, city_id: str, budget: int, category_listings: dict) -> str:
    """Generate a helpful no_match message."""
    city_names = {"taganrog": "Таганрог", "rostov-na-donu": "Ростов-на-Дону", "azov": "Азов"}
    city_name = city_names.get(city_id, city_id)
    cat_names = {
        "table": "столы",
        "chair": "кресла",
        "lamp": "лампы",
    }

    missing = [cat for cat, listings in category_listings.items() if not listings]
    if missing:
        parts = []
        for cat in missing:
            parts.append(f"в городе {city_name} нет {cat_names.get(cat, cat)}")
        message = " + ".join(parts) + ". "
    else:
        message = f"В городе {city_name} "
        if categories:
            cat_list = ", ".join(cat_names.get(c, c) for c in categories)
            message += f"нет полного комплекта из {cat_list} "
        else:
            message += "не удалось подобрать комплект "

    if budget is not None and budget < 20000:
        message += f"по бюджету {budget} руб. Попробуйте увеличить бюджет или изменить состав комплекта."
    else:
        message += "по заданным параметрам. Попробуйте изменить бюджет, город или состав комплекта."

    return message


if __name__ == "__main__":
    raise SystemExit(main())
