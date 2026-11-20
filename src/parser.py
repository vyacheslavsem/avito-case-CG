"""Parse dialog history into structured requirements using LLM.

Pipeline: messages[] → LLM → {city_id, budget_rub, categories[], constraints{}}
          If missing → needs_clarify() → return clarify response.

API: google/gemma-4-31B-it via LLM_BASE_URL + LLM_API_KEY.
Output is strict JSON schema (llm-intent.schema.json).
"""
import os
import sys
import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Environment variables for LLM connection
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://sfedu-hackathon-ai-gateway.sfedu-hackathon-ai-gateway.workers.dev/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "google/gemma-4-31B-it")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_USER_AGENT = os.environ.get("LLM_USER_AGENT", "hackathon-team-01/1.0")

# Strict JSON schema for intent extraction
INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "city_id": {
            "type": ["string", "null"],
            "enum": ["taganrog", "rostov-na-donu", "azov", None],
            "description": "Buyer's city for self-pickup. null if not specified."
        },
        "budget_rub": {
            "type": ["integer", "null"],
            "minimum": 0,
            "description": "Total budget in rubles. null if not specified."
        },
        "categories": {
            "type": ["array", "null"],
            "items": {
                "type": "string",
                "enum": ["table", "chair", "lamp"]
            },
            "description": "List of requested product categories. null if not specified."
        },
        "constraints": {
            "type": ["object", "null"],
            "properties": {
                "width_cm": {
                    "type": ["object", "null"],
                    "properties": {
                        "min": {"type": ["integer", "null"], "minimum": 1},
                        "max": {"type": ["integer", "null"], "minimum": 1}
                    },
                    "additionalProperties": False
                },
                "adjustable_height": {
                    "type": ["boolean", "null"]
                },
                "color_temperature_k": {
                    "type": ["object", "null"],
                    "properties": {
                        "min": {"type": ["integer", "null"], "minimum": 1},
                        "max": {"type": ["integer", "null"], "minimum": 1}
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": False
        }
    },
    "required": ["city_id", "budget_rub", "categories", "constraints"],
    "additionalProperties": False
}

# Supported values
SUPPORTED_CITIES = ["taganrog", "rostov-na-donu", "azov"]
SUPPORTED_CATEGORIES = ["table", "chair", "lamp"]


def build_system_prompt() -> str:
    """Build the system prompt for intent extraction."""
    return (
        "Ты — помощник покупателя. Твоя задача — извлечь условия покупки из диалога. "
        "Всегда возвращай только JSON по схеме. "
        "\n\n"
        "Города (city_id): taganrog, rostov-na-donu, azov. "
        "Если город не назван или называется иначе — верни null."
        "\n\n"
        "Категории (categories): table, chair, lamp. "
        "Если не названы — верни null."
        "\n\n"
        "Бюджет (budget_rub): общий верхний предел в рублях. "
        "Если не назван — верни null. Если несколько чисел — бери максимальный верхний предел."
        "\n\n"
        "Ограничения по характеристикам (constraints):"
        "  - width_cm (стол): {'min': int, 'max': int}. "
        "    'до', 'не более', 'не шире' = max включительно; "
        "    'менее', 'меньше', 'уже' = strict (используй max без границы)."
        "  - adjustable_height (кресло): true (есть регулировка), false (нет)."
        "  - color_temperature_k (лампа): {'min': int, 'max': int}. "
        "    Аналогичные правила границ как width_cm."
        "\n\n"
        "Правила:"
        "1. Учитывай ВСЮ историю диалога. Новые условия заменяют старые по тем же полям."
        "2. Если условие явно задано — используй его. Если нет — верни null."
        "3. Только structured JSON. Без пояснений."
        "4. Для диапазонов: если сказано 'от X до Y' — min=X, max=Y."
    )


def build_user_prompt(messages: list[dict]) -> str:
    """Build user prompt from dialog history."""
    parts = ["История диалога:\n"]
    for msg in messages:
        role = msg["role"]
        text = msg["text"]
        if role == "user":
            parts.append(f"Покупатель: {text}")
        elif role == "assistant":
            parts.append(f"Помощник: {text}")
    parts.append("\nИзвлеки условия и верни JSON.")
    return "\n".join(parts)


def call_llm(messages: list[dict]) -> Optional[dict]:
    """Call LLM API and parse intent from response.

    Returns:
        dict with keys: city_id, budget_rub, categories, constraints
        or None on error (caller should return 'clarify').
    """
    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY not set, cannot call LLM")
        return None

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(messages)

    # Check prompt size
    prompt_size = len((system_prompt + user_prompt).encode("utf-8"))
    if prompt_size > 32000:
        logger.warning(f"Prompt too large ({prompt_size} bytes), truncating user messages")
        # Keep only last 5 messages to fit
        truncated_messages = messages[-5:] if len(messages) > 5 else messages
        user_prompt = build_user_prompt(truncated_messages)

    body = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 256,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "buyer_requirements",
                "strict": True,
                "schema": INTENT_SCHEMA
            }
        },
        "stream": False,
        "n": 1
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": LLM_USER_AGENT,
    }

    try:
        logger.info("Calling LLM API for intent extraction")
        response = requests.post(
            LLM_BASE_URL.rstrip("/") + "/chat/completions",
            json=body,
            headers=headers,
            timeout=90,
        )

        if response.status_code == 401:
            logger.error("LLM API: 401 Unauthorized. Check LLM_API_KEY")
            return None
        elif response.status_code == 403:
            logger.error("LLM API: 403 Forbidden. Access may be expired")
            return None
        elif response.status_code == 429:
            logger.error("LLM API: 429 Rate limit exceeded")
            return None
        elif response.status_code != 200:
            logger.error(f"LLM API: {response.status_code} - {response.text[:500]}")
            return None

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            logger.error("LLM API: empty content in response")
            return None

        # Parse JSON string from response
        try:
            intent = json.loads(content)
            logger.info(f"LLM parsed intent: {intent}")
            return intent
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}")
            logger.error(f"Raw content: {content[:500]}")
            return None

    except requests.exceptions.Timeout:
        logger.error("LLM API: request timeout (90s)")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"LLM API: connection error: {e}")
        return None
    except Exception as e:
        logger.error(f"LLM API: unexpected error: {e}")
        return None


def parse_request(messages: list[dict]) -> dict:
    """Call LLM to extract requirements from dialog history.

    Args:
        messages: list of {role, text} from request.

    Returns:
        dict with keys: city_id, budget_rub, categories, constraints.
        Missing values are None/empty — caller must return 'clarify' if needed.
    """
    logger.info(f"Parsing request with {len(messages)} messages")

    intent = call_llm(messages)

    if intent is None:
        logger.warning("LLM call failed, returning empty requirements")
        return {
            "city_id": None,
            "budget_rub": None,
            "categories": [],
            "constraints": {},
        }

    # Validate and normalize
    city_id = intent.get("city_id")
    if city_id not in SUPPORTED_CITIES:
        city_id = None

    budget_rub = intent.get("budget_rub")
    if budget_rub is not None and (not isinstance(budget_rub, int) or budget_rub < 0):
        budget_rub = None

    categories = intent.get("categories")
    if categories is None:
        categories = []
    elif not isinstance(categories, list):
        categories = []
    else:
        # Filter to supported categories only
        categories = [c for c in categories if c in SUPPORTED_CATEGORIES]

    constraints = intent.get("constraints") or {}
    if not isinstance(constraints, dict):
        constraints = {}

    return {
        "city_id": city_id,
        "budget_rub": budget_rub,
        "categories": categories,
        "constraints": constraints,
    }


def needs_clarify(requirements: dict) -> list[dict]:
    """Return list of questions for missing main conditions.

    Returns:
        List of {field, text} for each missing condition.
        Empty list means all conditions are present.
    """
    questions = []

    if not requirements.get("categories"):
        questions.append({
            "field": "categories",
            "text": "Какие категории товаров вас интересуют? (table, chair, lamp)",
        })

    if not requirements.get("city_id"):
        questions.append({
            "field": "city_id",
            "text": "В каком городе вам нужен самовывоз? (taganrog, rostov-na-donu, azov)",
        })

    if requirements.get("budget_rub") is None:
        questions.append({
            "field": "budget_rub",
            "text": "Какой у вас бюджет на весь комплект? (в рублях)",
        })

    return questions
