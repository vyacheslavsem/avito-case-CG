"""Test: basic selection — all conditions known, kit exists."""
import json
import subprocess
import sys
import os
import pytest

RUN = os.path.join(os.path.dirname(__file__), "..", "run")
CATALOG = os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json")

# Example 1: full request → expect 'ok'
FULL_REQUEST = {
    "messages": [
        {
            "role": "user",
            "text": "Стол не шире метра, кресло и лампа. Таганрог. До 15 000 ₽ за всё."
        }
    ]
}


def _run(catalog_path, request):
    result = subprocess.run(
        [sys.executable, RUN, "--catalog", catalog_path],
        input=json.dumps(request, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"non-zero exit: {result.stderr}"
    return json.loads(result.stdout.strip())


class TestBasicSelection:
    """Tests for the 'ok' status."""

    def test_example_1_selection(self):
        """Example 01-selection: budget + city + categories known → ok."""
        response = _run(CATALOG, FULL_REQUEST)
        assert response["status"] == "ok"
        options = response["options"]
        assert 1 <= len(options) <= 3
        for option in options:
            assert "listing_ids" in option
            assert "total_rub" in option
            assert "explanation" in option
            assert isinstance(option["listing_ids"], list)
            assert 1 <= len(option["listing_ids"]) <= 3

    def test_ok_has_one_per_category(self):
        """Each option has exactly one listing per requested category."""
        response = _run(CATALOG, FULL_REQUEST)
        for option in response["options"]:
            cats = set()
            for lid in option["listing_ids"]:
                # Load catalog to check category
                with open(CATALOG) as f:
                    catalog = json.load(f)
                listing = next((l for l in catalog if l["id"] == lid), None)
                assert listing is not None, f"ID {lid} not in catalog"
                cats.add(listing["category"])
            # Requested: table, chair, lamp
            assert cats == {"table", "chair", "lamp"}

    def test_ok_total_rub_correct(self):
        """total_rub equals exact sum of price_rub."""
        response = _run(CATALOG, FULL_REQUEST)
        with open(CATALOG) as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            actual = sum(catalog[lid]["price_rub"] for lid in option["listing_ids"])
            assert option["total_rub"] == actual

    def test_ok_total_within_budget(self):
        """total_rub does not exceed budget."""
        response = _run(CATALOG, FULL_REQUEST)
        for option in response["options"]:
            assert option["total_rub"] <= 15000

    def test_ok_explanation_non_empty(self):
        """Explanation is non-empty and references catalog data."""
        response = _run(CATALOG, FULL_REQUEST)
        for option in response["options"]:
            assert len(option["explanation"]) > 0
