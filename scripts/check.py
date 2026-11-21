#!/usr/bin/env python3
"""Check request.json / response.json pairs by running the submitted CLI.

For the two public dialogs, also verify each recommendation against the
independently specified buyer requirements. For other pairs, the example
kit supplies the expected city and categories, but neither budget nor bounds.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "tz" / "examples"
sys.path.insert(0, str(ROOT))

from src.runner import reject_constant, unique_keys
from src.validator import validate_response, validate_response_shape


def read_json(data: bytes):
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_keys,
                      parse_constant=reject_constant)


def public_dialogs() -> list[tuple[dict, dict]]:
    cases = []
    for name, budget in (("01-selection", 15000), ("02-clarification", None)):
        request = read_json((EXAMPLES / name / "request.json").read_bytes())
        cases.append((request, {
            "categories": ["table", "chair", "lamp"],
            "city_id": "taganrog",
            "budget_rub": budget,
            "constraints": {"width_cm": {"max": 100}},
        }))
    return cases


def run_case(run_path: Path, catalog_path: Path, raw_request: bytes):
    command = [str(run_path), "--catalog", str(catalog_path)]
    if os.name == "nt" and (run_path == ROOT / "run" or run_path.suffix == ".py"):
        command.insert(0, sys.executable)
    result = subprocess.run(command, input=raw_request, capture_output=True, timeout=120)
    if result.returncode:
        diagnostic = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"run exited with {result.returncode}: {diagnostic}")
    return read_json(result.stdout)


def check_example(response, expected, request, catalog, requirements=None) -> list[str]:
    errors = validate_response_shape(expected)
    if errors:
        return ["invalid example response: " + "; ".join(errors)]
    errors = validate_response_shape(response)
    if errors:
        return errors
    if response["status"] != expected["status"]:
        return [f"expected status {expected['status']}, got {response['status']}"]
    if requirements is not None:
        errors.extend(validate_response(response, catalog, request, requirements))
    if expected["status"] == "clarify":
        expected_fields = {q["field"] for q in expected["questions"]}
        if {q["field"] for q in response["questions"]} != expected_fields:
            errors.append(f"expected clarification fields {sorted(expected_fields)}")
    elif expected["status"] == "ok" and requirements is None:
        by_id = {item["id"]: item for item in catalog}
        try:
            reference = [by_id[item] for item in expected["options"][0]["listing_ids"]]
            for option in response["options"]:
                items = [by_id[item] for item in option["listing_ids"]]
                if sorted(i["category"] for i in items) != sorted(i["category"] for i in reference):
                    errors.append("kit categories differ from the example")
                if {i["city_id"] for i in items} != {i["city_id"] for i in reference}:
                    errors.append("kit city differs from the example")
                if sum(i["price_rub"] for i in items) != option["total_rub"]:
                    errors.append("kit price differs from the catalog")
        except KeyError as exc:
            errors.append(f"missing catalog ID or field: {exc}")
    return errors


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", "-d", type=Path, default=EXAMPLES)
    parser.add_argument("--catalog", type=Path, default=ROOT / "docs/tz/data/catalog.json")
    parser.add_argument("--run", type=Path, default=ROOT / "run")
    args = parser.parse_args()
    files = sorted(args.directory.rglob("request.json"))
    if not files:
        logging.error("No request.json files found in %s", args.directory)
        return 1
    try:
        catalog = read_json(args.catalog.read_bytes())
        known_dialogs = public_dialogs()
    except (OSError, ValueError) as exc:
        logging.error("Cannot read checker inputs: %s", exc)
        return 1

    passed = 0
    for path in files:
        try:
            raw_request = path.read_bytes()
            request = read_json(raw_request)
            expected = read_json(path.with_name("response.json").read_bytes())
            requirements = next((req for dialog, req in known_dialogs if dialog == request), None)
            response = run_case(args.run.resolve(), args.catalog.resolve(), raw_request)
            errors = check_example(response, expected, request, catalog, requirements)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            errors = [str(exc)]
        if errors:
            logging.error("FAIL %s: %s", path.parent.name, "; ".join(errors))
        else:
            logging.info("PASS %s", path.parent.name)
            passed += 1
    logging.info("Results: %d/%d passed", passed, len(files))
    return int(passed != len(files))


if __name__ == "__main__":
    raise SystemExit(main())
