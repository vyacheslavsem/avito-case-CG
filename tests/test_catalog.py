"""Test: catalog.py module unit tests."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.catalog import load_catalog, filter_by_city, filter_by_category


CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json")


class TestLoadCatalog:
    def test_load_returns_list(self):
        catalog = load_catalog(CATALOG_PATH)
        assert isinstance(catalog, list)
        assert len(catalog) > 0

    def test_each_listing_has_required_fields(self):
        catalog = load_catalog(CATALOG_PATH)
        required = {"id", "category", "title", "description", "price_rub", "city_id", "attributes"}
        for listing in catalog:
            assert required.issubset(listing.keys()), f"Missing fields in {listing.get('id')}"

    def test_all_categories_present(self):
        catalog = load_catalog(CATALOG_PATH)
        categories = {l["category"] for l in catalog}
        assert categories == {"table", "chair", "lamp"}


class TestFilterByCity:
    def test_filters_correctly(self):
        catalog = load_catalog(CATALOG_PATH)
        taganrog = filter_by_city(catalog, "taganrog")
        for l in taganrog:
            assert l["city_id"] == "taganrog"

    def test_empty_result_for_unknown_city(self):
        catalog = load_catalog(CATALOG_PATH)
        result = filter_by_city(catalog, "unknown-city")
        assert result == []


class TestFilterByCategory:
    def test_tables_only(self):
        catalog = load_catalog(CATALOG_PATH)
        tables = filter_by_category(catalog, "table")
        for l in tables:
            assert l["category"] == "table"

    def test_chairs_only(self):
        catalog = load_catalog(CATALOG_PATH)
        chairs = filter_by_category(catalog, "chair")
        for l in chairs:
            assert l["category"] == "chair"
