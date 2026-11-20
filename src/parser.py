"""Parse dialog history into structured requirements using LLM.

Expected LLM output schema:
{
    "city_id": "taganrog" | "rostov-na-donu" | "azov" | null,
    "budget_rub": int | null,
    "categories": ["table" | "chair" | "lamp", ...],
    "constraints": {
        "width_cm": {"min": int | null, "max": int | null},
        "adjustable_height": bool | null,
        "color_temperature_k": {"min": int | null, "max": int | null}
    }
}
"""
import os
import sys
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def parse_request(messages: list[dict]) -> dict:
    """Call LLM to extract requirements from dialog history.

    Returns dict with keys: city_id, budget_rub, categories, constraints.
    Missing values are None — caller must return 'clarify' if needed.
    """
    # TODO: implement LLM call using requests + env vars
    # TODO: construct system prompt + user messages
    # TODO: parse and validate JSON response
    # TODO: handle API errors (retry, fallback)
    logger.info("parser.py: placeholder — not yet implemented")
    return {
        "city_id": None,
        "budget_rub": None,
        "categories": [],
        "constraints": {},
    }


def needs_clarify(requirements: dict) -> list[dict]:
    """Return list of questions for missing main conditions."""
    questions = []
    if not requirements.get("categories"):
        questions.append({
            "field": "categories",
            "text": "Какие категории товаров вас интересуют?",
        })
    if not requirements.get("city_id"):
        questions.append({
            "field": "city_id",
            "text": "В каком городе вам нужен самовывоз?",
        })
    if requirements.get("budget_rub") is None:
        questions.append({
            "field": "budget_rub",
            "text": "Какой у вас бюджет на весь комплект?",
        })
    return questions
