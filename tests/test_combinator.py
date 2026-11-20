"""Tests for combinator module."""
import pytest
from src.combinator import build_combinations, _generate_explanation


# Sample test data
TABLE_LISTINGS = [
    {"id": "t1", "category": "table", "title": "Стол 1", "price_rub": 5000, "attributes": {"width_cm": 80}},
    {"id": "t2", "category": "table", "title": "Стол 2", "price_rub": 6000, "attributes": {"width_cm": 100}},
    {"id": "t3", "category": "table", "title": "Стол 3", "price_rub": 7000, "attributes": {"width_cm": 120}},
]

CHAIR_LISTINGS = [
    {"id": "c1", "category": "chair", "title": "Кресло 1", "price_rub": 3000, "attributes": {"adjustable_height": True}},
    {"id": "c2", "category": "chair", "title": "Кресло 2", "price_rub": 4000, "attributes": {"adjustable_height": False}},
]

LAMP_LISTINGS = [
    {"id": "l1", "category": "lamp", "title": "Лампа 1", "price_rub": 1500, "attributes": {"color_temperature_k": 4000}},
    {"id": "l2", "category": "lamp", "title": "Лампа 2", "price_rub": 2000, "attributes": {"color_temperature_k": 5000}},
]


class TestBuildCombinations:
    """Tests for build_combinations function."""

    def test_single_category(self):
        """Test with only one category."""
        category_listings = {"table": TABLE_LISTINGS}
        budget = 6500

        result = build_combinations(category_listings, budget)

        assert len(result) == 2  # t1 (5000) and t2 (6000) fit budget
        assert result[0]["total_rub"] == 5000
        assert result[0]["listing_ids"] == ["t1"]
        assert result[1]["total_rub"] == 6000
        assert result[1]["listing_ids"] == ["t2"]

    def test_multiple_categories(self):
        """Test with multiple categories."""
        category_listings = {
            "table": TABLE_LISTINGS,
            "chair": CHAIR_LISTINGS,
        }
        budget = 10000

        result = build_combinations(category_listings, budget, max_options=10)

        # All combos where total <= 10000
        # t1+c1 = 8000, t1+c2 = 9000, t2+c1 = 9000, t2+c2 = 10000, t3+c1 = 10000
        assert len(result) == 5
        assert result[0]["total_rub"] == 8000
        assert set(result[0]["listing_ids"]) == {"t1", "c1"}
        assert result[-1]["total_rub"] == 10000

    def test_budget_constraint(self):
        """Test that combos exceeding budget are filtered."""
        category_listings = {
            "table": TABLE_LISTINGS,
            "chair": CHAIR_LISTINGS,
        }
        budget = 8500

        result = build_combinations(category_listings, budget)

        # Only t1+c1 (8000) fits
        assert len(result) == 1
        assert result[0]["total_rub"] == 8000

    def test_no_budget_limit(self):
        """Test with no budget constraint."""
        category_listings = {
            "table": TABLE_LISTINGS[:1],  # Only t1
            "chair": CHAIR_LISTINGS,
        }

        result = build_combinations(category_listings, budget=None)

        assert len(result) == 2  # t1+c1 and t1+c2
        assert result[0]["total_rub"] == 8000  # 5000 + 3000
        assert result[1]["total_rub"] == 9000  # 5000 + 4000

    def test_max_options(self):
        """Test that max_options limits the result."""
        category_listings = {
            "table": TABLE_LISTINGS,
            "chair": CHAIR_LISTINGS,
        }
        budget = 20000  # No budget constraint

        result = build_combinations(category_listings, budget, max_options=2)

        assert len(result) == 2
        assert result[0]["total_rub"] < result[1]["total_rub"]

    def test_no_valid_combos(self):
        """Test when no combos fit the budget."""
        category_listings = {
            "table": TABLE_LISTINGS,
            "chair": CHAIR_LISTINGS,
        }
        budget = 5000  # Too low for any combo

        result = build_combinations(category_listings, budget)

        assert result == []

    def test_empty_category_listings(self):
        """Test with empty category listings."""
        result = build_combinations({}, budget=10000)
        assert result == []

    def test_zero_budget(self):
        """Test with zero budget."""
        category_listings = {
            "table": [{"id": "t1", "category": "table", "title": "Стол", "price_rub": 0, "attributes": {}}],
        }

        result = build_combinations(category_listings, budget=0)

        assert len(result) == 1
        assert result[0]["total_rub"] == 0

    def test_price_sorting(self):
        """Test that results are sorted by price (cheapest first)."""
        category_listings = {
            "table": TABLE_LISTINGS,
            "chair": CHAIR_LISTINGS,
            "lamp": LAMP_LISTINGS,
        }
        budget = 20000

        result = build_combinations(category_listings, budget)

        for i in range(len(result) - 1):
            assert result[i]["total_rub"] <= result[i + 1]["total_rub"]

    def test_unique_listing_ids_in_option(self):
        """Test that listing_ids within an option are unique."""
        # Even though we pick one per category, verify uniqueness
        category_listings = {
            "table": TABLE_LISTINGS,
            "chair": CHAIR_LISTINGS,
        }
        budget = 20000

        result = build_combinations(category_listings, budget)

        for option in result:
            assert len(option["listing_ids"]) == len(set(option["listing_ids"]))

    def test_explanation_present(self):
        """Test that explanations are generated."""
        category_listings = {
            "table": TABLE_LISTINGS[:1],
            "chair": CHAIR_LISTINGS[:1],
        }
        budget = 10000

        result = build_combinations(category_listings, budget)

        assert len(result) == 1
        assert len(result[0]["explanation"]) > 0
        assert "Стол" in result[0]["explanation"]
        assert "Кресло" in result[0]["explanation"]

    def test_exact_budget_match(self):
        """Test that exact budget match is included."""
        category_listings = {
            "table": [{"id": "t1", "category": "table", "title": "Стол", "price_rub": 5000, "attributes": {}}],
            "chair": [{"id": "c1", "category": "chair", "title": "Кресло", "price_rub": 5000, "attributes": {}}],
        }

        result = build_combinations(category_listings, budget=10000)

        assert len(result) == 1
        assert result[0]["total_rub"] == 10000

    def test_value_error_on_empty_category(self):
        """Test that ValueError is raised when a category has no listings."""
        category_listings = {
            "table": TABLE_LISTINGS,
            "chair": [],  # Empty
        }

        with pytest.raises(ValueError, match="No listings available for category"):
            build_combinations(category_listings, budget=20000)


class TestExplanationGeneration:
    """Tests for explanation generation."""

    def test_table_with_width(self):
        """Test explanation for table with width attribute."""
        combo = (TABLE_LISTINGS[0],)
        categories = ["table"]

        explanation = _generate_explanation(combo, categories)

        assert "Стол" in explanation
        assert "80 см" in explanation
        assert "5000 руб" in explanation

    def test_chair_with_adjustable_height(self):
        """Test explanation for chair with adjustable_height."""
        combo = (CHAIR_LISTINGS[0],)
        categories = ["chair"]

        explanation = _generate_explanation(combo, categories)

        assert "Кресло" in explanation
        assert "с регулировкой высоты" in explanation

    def test_lamp_with_color_temperature(self):
        """Test explanation for lamp with color_temperature_k."""
        combo = (LAMP_LISTINGS[0],)
        categories = ["lamp"]

        explanation = _generate_explanation(combo, categories)

        assert "Лампа" in explanation
        assert "4000 К" in explanation

    def test_multi_category_explanation(self):
        """Test explanation for multi-category kit."""
        combo = (TABLE_LISTINGS[0], CHAIR_LISTINGS[0], LAMP_LISTINGS[0])
        categories = ["table", "chair", "lamp"]

        explanation = _generate_explanation(combo, categories)

        assert "Комплект:" in explanation
        assert "Стол" in explanation
        assert "Кресло" in explanation
        assert "Лампа" in explanation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
