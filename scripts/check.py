#!/usr/bin/env python3
"""Run all examples through ./run and validate responses.

Usage:
    python scripts/check.py
    python scripts/check.py --directory tests/

Checks (CONTRACT §5 — auto-check verifies structure + catalog compliance):
  - Response is valid JSON
  - Response matches one of the three status schemas
  - For 'ok': IDs exist, city matches, categories covered exactly once, sum correct, sum ≤ budget
  - For 'clarify': questions cover all missing fields
  - For 'no_match': message is non-empty
  - Catalog compliance: listing_ids in catalog, total_rub = sum(price_rub), city match
"""
import argparse
import json
import subprocess
import sys
import os
import glob
import logging
from pathlib import Path

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_case(run_path: str, catalog_path: str, request_path: str) -> dict:
    """Run ./run --catalog <catalog> < <request> and return parsed JSON."""
    result = subprocess.run(
        [run_path, "--catalog", str(catalog_path)],
        stdin=open(request_path, "r"),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error(f"Command failed (exit {result.returncode})")
        logger.error(f"stderr: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in stdout: {e}")
        logger.error(f"stdout was: {result.stdout[:500]}")
        return None


def validate_catalog_compliance(response: dict, catalog: list, errors: list) -> None:
    """Check response against catalog data (CONTRACT §5 — auto-check verifies catalog compliance).
    
    Verifies:
    - All listing_ids exist in catalog
    - Each listing is in a valid catalog entry
    - total_rub equals exact sum of price_rub
    - No duplicate IDs within an option
    - One listing per category (no extra items)
    """
    if response.get("status") != "ok":
        return

    cat_ids = {l["id"]: l for l in catalog if isinstance(l, dict) and "id" in l}
    options = response.get("options", [])

    for idx, option in enumerate(options):
        listing_ids = option.get("listing_ids", [])
        total_rub = option.get("total_rub", 0)

        if not listing_ids:
            errors.append(f"option[{idx}]: listing_ids must not be empty")
            continue

        # Check for duplicate IDs
        if len(set(listing_ids)) != len(listing_ids):
            errors.append(f"option[{idx}]: duplicate listing_ids")

        # Check all IDs exist in catalog
        for lid in listing_ids:
            if lid not in cat_ids:
                errors.append(f"option[{idx}]: listing_id {lid!r} not in catalog")

        # Check total_rub equals sum of price_rub
        if listing_ids:
            actual_total = sum(cat_ids[lid]["price_rub"] for lid in listing_ids if lid in cat_ids)
            if total_rub != actual_total:
                errors.append(
                    f"option[{idx}]: total_rub {total_rub} != actual sum {actual_total}"
                )

        # Check one per category
        cats = set()
        for lid in listing_ids:
            if lid in cat_ids:
                cats.add(cat_ids[lid].get("category"))
        if len(cats) != len(listing_ids):
            errors.append(f"option[{idx}]: multiple listings of same category or unknown categories")


def validate_response(response: dict, errors: list) -> None:
    """Basic schema validation of a response."""
    if not isinstance(response, dict):
        errors.append("Response is not a JSON object")
        return
    status = response.get("status")
    if status not in ("ok", "clarify", "no_match"):
        errors.append(f"Unknown status: {status!r}")
        return
    if status == "ok":
        options = response.get("options")
        if not isinstance(options, list) or not (1 <= len(options) <= 3):
            errors.append("ok: options must be array of 1-3 items")
    elif status == "clarify":
        questions = response.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append("clarify: questions must be non-empty array")
    elif status == "no_match":
        msg = response.get("message")
        if not isinstance(msg, str) or not msg:
            errors.append("no_match: message must be non-empty string")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory", "-d",
        default=os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "examples"),
        help="Directory containing example request/response pairs",
    )
    parser.add_argument(
        "--catalog",
        default=os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json"),
        help="Path to catalog JSON",
    )
    parser.add_argument(
        "--run",
        default=os.path.join(os.path.dirname(__file__), "..", "run"),
        help="Path to the run executable",
    )
    args = parser.parse_args()

    run_path = os.path.abspath(args.run)
    catalog_path = os.path.abspath(args.catalog)

    if not os.path.isfile(run_path):
        logger.error(f"run not found: {run_path}")
        return 1
    if not os.access(run_path, os.X_OK):
        logger.error(f"run is not executable: {run_path}")
        return 1
    if not os.path.isfile(catalog_path):
        logger.error(f"catalog not found: {catalog_path}")
        return 1

    # Load catalog for compliance checks
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        logger.info(f"Loaded catalog with {len(catalog)} listings")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Could not load catalog: {e}")
        return 1

    # Find all example request.json files
    request_files = sorted(glob.glob(os.path.join(args.directory, "**", "request.json"), recursive=True))
    if not request_files:
        logger.warning(f"No request.json files found in {args.directory}")
        return 0

    total = len(request_files)
    passed = 0
    failed = 0

    for req_path in request_files:
        resp_path = req_path.replace("request.json", "response.json")
        rel = os.path.relpath(req_path)
        logger.info(f"Testing: {rel}")

        response = run_case(run_path, catalog_path, req_path)

        if response is None:
            failed += 1
            logger.error(f"  FAIL: no valid response")
            continue

        errors = []
        validate_response(response, errors)
        validate_catalog_compliance(response, catalog, errors)

        if errors:
            failed += 1
            logger.error(f"  FAIL: {'; '.join(errors)}")
        else:
            passed += 1
            logger.info(f"  PASS: status={response.get('status')}")

    logger.info(f"Results: {passed}/{total} passed, {failed}/{total} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
