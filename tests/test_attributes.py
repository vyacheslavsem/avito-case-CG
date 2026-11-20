"""Test: attribute constraints — width bounds, adjustability, color temperature."""
import json
import subprocess
import sys
import os
import pytest

RUN = os.path.join(os.path.dirname(__file__), "..", "run")
CATALOG = os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json")

# Table narrower than 80cm (strict boundary: "уже 80")
STRICT_BOUNDARY_REQUEST = {
    "messages": [
        {
            "role": "user",
            "text": "Стол уже 80 см, кресло с регулировкой высоты. Таганрог. До 10000 ₽."
        }
    ]
}

# Chair with adjustable height required
ADJUSTABLE_CHAIR_REQUEST = {
    "messages": [
        {
            "role": "user",
            "text": "Кресло с регулировкой высоты. Таганрог. До 5000 ₽."
        }
    ]
}

# Chair WITHOUT adjustable height
NO_ADJUSTABLE_CHAIR_REQUEST = {
    "messages": [
        {
            "role": "user",
            "text": "Кресло без регулировки высоты. Таганрог. До 5000 ₽."
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
    if result.returncode != 0:
        print(f"stderr: {result.stderr}", file=sys.stderr)
    assert result.returncode == 0, f"non-zero exit: {result.stderr}"
    return json.loads(result.stdout.strip())


class TestAttributeConstraints:
    """Tests for attribute filtering."""

    def test_width_boundary(self):
        """'уже 80' means strictly less than 80cm."""
        response = _run(CATALOG, STRICT_BOUNDARY_REQUEST)
        assert response["status"] == "ok"
        with open(CATALOG) as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            for lid in option["listing_ids"]:
                l = catalog[lid]
                if l["category"] == "table":
                    assert l["attributes"].get("width_cm") is not None
                    assert l["attributes"]["width_cm"] < 80

    def test_chair_adjustable(self):
        """'с регулировкой высоты' means adjustable_height=true."""
        response = _run(CATALOG, ADJUSTABLE_CHAIR_REQUEST)
        assert response["status"] == "ok"
        with open(CATALOG) as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            for lid in option["listing_ids"]:
                l = catalog[lid]
                if l["category"] == "chair":
                    assert l["attributes"].get("adjustable_height") is True

    def test_chair_not_adjustable(self):
        """'без регулировки высоты' means adjustable_height=false."""
        response = _run(CATALOG, NO_ADJUSTABLE_CHAIR_REQUEST)
        assert response["status"] == "ok"
        with open(CATALOG) as f:
            catalog = {l["id"]: l for l in json.load(f)}
        for option in response["options"]:
            for lid in option["listing_ids"]:
                l = catalog[lid]
                if l["category"] == "chair":
                    assert l["attributes"].get("adjustable_height") is False
