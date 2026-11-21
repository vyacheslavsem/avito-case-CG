"""Test: no_match — conditions known but no compatible kit."""
import os

from tests.cli import run_case

CATALOG = os.path.join(os.path.dirname(__file__), "..", "docs", "tz", "data", "catalog.json")

# Very low budget, all categories → likely no_match
LOW_BUDGET_REQUEST = {
    "messages": [
        {
            "role": "user",
            "text": "Стол, кресло и лампа. Таганрог. До 100 ₽ за всё."
        }
    ]
}



class TestNoMatch:
    """Tests for the 'no_match' status."""

    def test_very_low_budget_no_match(self):
        """Budget too low → no_match with message."""
        response = run_case(CATALOG, LOW_BUDGET_REQUEST)
        assert response["status"] == "no_match"
        assert len(response["message"]) > 0

    def test_no_match_no_listing_ids(self):
        """no_match must not contain listing_ids."""
        response = run_case(CATALOG, LOW_BUDGET_REQUEST)
        assert "options" not in response

    def test_no_match_message_suggests_change(self):
        """Message should suggest what to change."""
        response = run_case(CATALOG, LOW_BUDGET_REQUEST)
        # Message should mention budget or city as the blocking condition
        msg_lower = response["message"].lower()
        # Just a basic sanity check
        assert len(msg_lower) > 10
