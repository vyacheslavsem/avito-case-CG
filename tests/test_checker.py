"""Regression checks for the public-example checker, independent of the LLM."""
import json
import sys

import pytest

from scripts import check


@pytest.fixture
def catalog():
    return check.read_json((check.ROOT / "docs/tz/data/catalog.json").read_bytes())


def option(catalog, ids):
    prices = {item["id"]: item["price_rub"] for item in catalog}
    return {"status": "ok", "options": [{
        "listing_ids": ids,
        "total_rub": sum(prices[item_id] for item_id in ids),
        "explanation": "Each selected item is available for pickup in the requested city.",
    }]}


def check_public(name, response, catalog):
    case = check.EXAMPLES / name
    request = check.read_json((case / "request.json").read_bytes())
    expected = check.read_json((case / "response.json").read_bytes())
    requirements = next(req for dialog, req in check.public_dialogs() if dialog == request)
    return check.check_example(response, expected, request, catalog, requirements)


def test_valid_alternative_kit(catalog):
    response = option(catalog, ["demo-1-1-04", "demo-1-2-03", "demo-1-3-02"])
    assert check_public("01-selection", response, catalog) == []


@pytest.mark.parametrize("ids", [
    ["demo-1-1-05", "c04", "l09"],  # table wider than one metre
    ["demo-2-1-10", "c04", "l09"],  # another city
    ["demo-1-1-09", "demo-1-2-08", "demo-1-3-07"],  # 16000 rubles
    ["c04", "l09"],  # missing category
])
def test_ineligible_kit(catalog, ids):
    assert check_public("01-selection", option(catalog, ids), catalog)


def test_extra_clarification_field(catalog):
    response = {"status": "clarify", "questions": [
        {"field": "budget_rub", "text": "Budget?"},
        {"field": "city_id", "text": "City?"},
    ]}
    assert check_public("02-clarification", response, catalog)
    response["questions"].pop()
    assert check_public("02-clarification", response, catalog) == []


def test_custom_example_accepts_alternative_ids(catalog):
    expected = option(catalog, ["t12"])
    response = option(catalog, ["demo-1-1-04"])
    assert check.check_example(response, expected, {}, catalog) == []
    response["options"][0]["total_rub"] += 1
    assert check.check_example(response, expected, {}, catalog)


@pytest.mark.parametrize("raw", [b'{"status":1,"status":2}', b'{"x":NaN}'])
def test_invalid_json_rejected(raw):
    with pytest.raises(ValueError):
        check.read_json(raw)


def test_wrong_status_fails_checker_cli(monkeypatch, tmp_path):
    script = tmp_path / "constant.py"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\nsys.stdin.buffer.read()\n"
        f"print({json.dumps({'status': 'no_match', 'message': 'No kit'})!r})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    monkeypatch.setattr(sys, "argv", ["check", "--run", str(script)])
    assert check.main() == 1


def test_empty_directory_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["check", "-d", str(tmp_path)])
    assert check.main() == 1
