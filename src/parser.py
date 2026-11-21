"""Parse dialog history into structured requirements using LLM.

Pipeline: messages[] → LLM → {city_id, budget_rub, categories[], constraints{}}
          If missing → needs_clarify() → return clarify response.

API: google/gemma-4-31B-it via LLM_BASE_URL + LLM_API_KEY.
Output is strict JSON schema (llm-intent.schema.json).
"""
import os
import json
import time

import requests
from urllib3.util import Timeout

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

class LLMError(Exception):
    """The gateway could not produce a usable intent for this dialog."""


# Supported values
SUPPORTED_CITIES = ["taganrog", "rostov-na-donu", "azov"]
SUPPORTED_CATEGORIES = ["table", "chair", "lamp"]


def build_system_prompt() -> str:
    """Build the system prompt for intent extraction."""
    return (
        "Извлеки из всей истории диалога действующие условия покупки и верни JSON по схеме. "
        "Учитывай уточнения и короткие ответы. Если покупатель изменил условие, новое "
        "значение заменяет старое для этого поля. Остальные поля сохраняй.\n"
        "categories — список всех запрошенных видов товаров, по одному ID на вид. "
        "Словарь: стол → table; стул или кресло → chair; лампа или светильник → lamp. "
        "Например, «стол до 100 см, кресло» → [\"table\",\"chair\"]; "
        "«только лампу» → [\"lamp\"]. Слова о размерах, регулировке и цвете — характеристики. "
        "Если виды товаров не определены или покупатель просит также товар вне словаря "
        "(например, стол и диван), верни categories=null.\n"
        "city_id: Таганрог → taganrog, Ростов-на-Дону → rostov-na-donu, Азов → azov. "
        "Для неизвестного, неназванного или неоднозначного города верни null. "
        "budget_rub — последняя явно указанная максимальная сумма в рублях за весь комплект, "
        "в том числе 0. Если она неясна, верни null. Не путай деньги с характеристиками.\n"
        "constraints: width_cm — ширина стола в сантиметрах (1 м = 100 см), "
        "color_temperature_k — температура лампы в кельвинах. Указывай min и/или max. "
        "До, не более, не шире X означают max=X; от, не менее X означают min=X. "
        "Уже, меньше X означают max=X-1; шире, больше X означают min=X+1. "
        "От X до Y включает обе границы. Точное значение задаёт обе границы. "
        "adjustable_height — true для кресла с регулировкой, false для кресла без неё. "
        "Заполняй лишь названные характеристики."
    )


def call_llm(messages: list[dict]) -> dict:
    """Submit the full dialog and decode the gateway's structured result."""
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set")

    history = [{"role": "system", "content": build_system_prompt()}]
    history.extend({"role": msg["role"], "content": msg["text"]} for msg in messages)
    if sum(len(msg["content"].encode("utf-8")) for msg in history) > 32768:
        raise LLMError("dialog exceeds the 32768-byte model input limit")

    body = {
        "model": LLM_MODEL,
        "messages": history,
        "max_tokens": 256,
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "buyer_requirements", "strict": True, "schema": INTENT_SCHEMA},
        },
        "stream": False,
        "n": 1,
    }
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > 65536:
        raise LLMError("request exceeds the 65536-byte HTTP body limit")

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": LLM_USER_AGENT,
    }
    # Leave time for local selection and writing stdout within the 120-second CLI budget.
    deadline = time.monotonic() + 105
    for attempt in range(2):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LLMError("model request timed out")
        try:
            response = requests.post(
                LLM_BASE_URL.rstrip("/") + "/chat/completions",
                data=payload,
                headers=headers,
                timeout=Timeout(connect=5, total=min(90, remaining)),
            )
        except requests.exceptions.RequestException as error:
            raise LLMError(f"model request failed ({type(error).__name__})") from None
        if response.status_code == 429 and attempt == 0:
            # Retry once only on an explicit delay. Time spent in the first
            # request reduces the allowance for both waiting and the second call.
            retry_after = response.headers.get("Retry-After", "")
            if retry_after.isascii() and retry_after.isdigit() and len(retry_after) <= 2:
                delay = int(retry_after)
                if delay <= 60 and delay + 5 < deadline - time.monotonic():
                    time.sleep(delay)
                    continue
        if response.status_code != 200:
            raise LLMError(f"model gateway returned HTTP {response.status_code}")
        break

    try:
        choice = response.json()["choices"][0]
        message = choice["message"]
        if choice["finish_reason"] != "stop" or message["role"] != "assistant":
            raise ValueError
        content = message["content"]
        if not isinstance(content, str):
            raise ValueError
        intent = json.loads(content, object_pairs_hook=_unique_fields)
    except (ValueError, KeyError, IndexError, TypeError):
        raise LLMError("malformed model response") from None
    return intent


def _unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("duplicate model field")
    return fields


def parse_request(messages: list[dict]) -> dict:
    """Return normalized conditions. Missing buyer conditions are represented by null."""
    intent = call_llm(messages)
    if not isinstance(intent, dict) or set(intent) != set(INTENT_SCHEMA["required"]):
        raise LLMError("invalid model intent fields")

    city = intent["city_id"]
    budget = intent["budget_rub"]
    categories = intent["categories"]
    if city is not None and not isinstance(city, str):
        raise LLMError("invalid model city")
    if budget is not None and (type(budget) is not int or budget < 0):
        raise LLMError("invalid model budget")
    if categories is None:
        categories = []
    if not isinstance(categories, list) or not all(isinstance(c, str) for c in categories):
        raise LLMError("invalid model categories")
    unsupported = any(c not in SUPPORTED_CATEGORIES for c in categories)
    constraints = intent["constraints"]
    if constraints is None:
        constraints = {}
    if not isinstance(constraints, dict):
        raise LLMError("invalid model constraints")

    normalized = {}
    for key, value in constraints.items():
        if key not in {"width_cm", "color_temperature_k", "adjustable_height"}:
            raise LLMError("unknown model constraint")
        if value is None:
            continue
        if key == "adjustable_height":
            if not isinstance(value, bool):
                raise LLMError("invalid model height adjustment")
            normalized[key] = value
        else:
            if not isinstance(value, dict) or value.keys() - {"min", "max"}:
                raise LLMError("invalid model range")
            bounds = {k: v for k, v in value.items() if v is not None}
            if any(type(v) is not int or v < 1 for v in bounds.values()):
                raise LLMError("invalid numeric model bound")
            if bounds:
                normalized[key] = bounds

    return {
        "city_id": city if city in SUPPORTED_CITIES else None,
        "budget_rub": budget,
        "categories": list(dict.fromkeys(c for c in categories if c in SUPPORTED_CATEGORIES)),
        "constraints": normalized,
        "_has_unsupported_categories": unsupported,
    }


def needs_clarify(requirements: dict) -> list[dict]:
    """Return list of questions for missing main conditions.

    Returns:
        List of {field, text} for each missing condition.
        Empty list means all conditions are present.
    """
    questions = []

    if not requirements.get("categories") or requirements.get("_has_unsupported_categories"):
        questions.append({
            "field": "categories",
            "text": "Какие категории товаров вас интересуют? (стол, кресло или лампа)",
        })

    if not requirements.get("city_id"):
        questions.append({
            "field": "city_id",
            "text": "В каком городе вам нужен самовывоз? (Таганрог, Ростов-на-Дону или Азов)",
        })

    if requirements.get("budget_rub") is None:
        questions.append({
            "field": "budget_rub",
            "text": "Какой у вас бюджет на весь комплект? (в рублях)",
        })

    return questions
