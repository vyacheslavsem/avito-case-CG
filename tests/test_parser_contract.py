"""Offline contract tests for the gateway boundary and dialog normalization."""
import json
from unittest.mock import Mock

import pytest
import requests

from src import parser


MESSAGES = [{"role": "user", "text": "Стол, Таганрог. До 5000."}]
INTENT = {"city_id": "taganrog", "categories": ["table"], "budget_rub": 5000, "constraints": {}}


def success(intent):
    reply = Mock(status_code=200)
    reply.json.return_value = {"choices": [{
        "finish_reason": "stop",
        "message": {"role": "assistant", "content": json.dumps(intent)},
    }]}
    return reply


@pytest.fixture
def post(monkeypatch):
    monkeypatch.setattr(parser, "LLM_API_KEY", "test-only")
    mock = Mock(return_value=success(INTENT))
    monkeypatch.setattr(parser.requests, "post", mock)
    return mock


def test_transmits_full_history_and_exact_utf8_bytes(post):
    history = MESSAGES + [{"role": "assistant", "text": "Бюджет прежний?"},
                          {"role": "user", "text": "Теперь до 3000. " + "я" * 12000}]
    parser.parse_request(history)
    payload = post.call_args.kwargs["data"]
    assert len(payload) <= 65536
    assert "Таганрог".encode() in payload
    body = json.loads(payload)
    assert body["messages"][1:] == [{"role": m["role"], "content": m["text"]} for m in history]


@pytest.mark.parametrize(("text", "limit"), [("я" * 18000, "32768"), ("\x01" * 12000, "65536")])
def test_oversized_input_is_rejected_before_http(post, text, limit):
    with pytest.raises(parser.LLMError, match=limit):
        parser.parse_request([{"role": "user", "text": text}])
    post.assert_not_called()


def test_missing_key_is_a_technical_error(post, monkeypatch):
    monkeypatch.setattr(parser, "LLM_API_KEY", "")
    with pytest.raises(parser.LLMError, match="LLM_API_KEY"):
        parser.parse_request(MESSAGES)
    post.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 429, 502, 503])
def test_service_failure_propagates(post, status):
    post.return_value = Mock(status_code=status, headers={}, text="sensitive diagnostic")
    with pytest.raises(parser.LLMError, match=str(status)) as caught:
        parser.parse_request(MESSAGES)
    assert "sensitive" not in str(caught.value)
    post.assert_called_once()


def test_timeout_sanitizes_request_error(post):
    post.side_effect = requests.Timeout("sensitive diagnostic")
    with pytest.raises(parser.LLMError, match="Timeout") as caught:
        parser.parse_request(MESSAGES)
    assert "sensitive" not in str(caught.value)


@pytest.mark.parametrize("intent", [
    None, [], {}, {**INTENT, "budget_rub": True}, {**INTENT, "constraints": []},
    {**INTENT, "constraints": {"width_cm": {"min": "90"}}},
])
def test_malformed_intent_is_a_technical_error(post, intent):
    post.return_value = success(intent)
    with pytest.raises(parser.LLMError):
        parser.parse_request(MESSAGES)


@pytest.mark.parametrize("content", ["", "{", '{"city_id":null,"city_id":null}'])
def test_invalid_model_json_does_not_become_clarification(post, content):
    post.return_value.json.return_value["choices"][0]["message"]["content"] = content
    with pytest.raises(parser.LLMError, match="malformed model response"):
        parser.parse_request(MESSAGES)


def test_short_retry_after_is_respected_once(post, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(parser.time, "sleep", sleep)
    post.side_effect = [Mock(status_code=429, headers={"Retry-After": "1"}), success(INTENT)]
    assert parser.parse_request(MESSAGES)["budget_rub"] == 5000
    sleep.assert_called_once_with(1)
    assert post.call_count == 2


def test_long_retry_after_finishes_without_sleep(post, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(parser.time, "sleep", sleep)
    post.return_value = Mock(status_code=429, headers={"Retry-After": "120"})
    with pytest.raises(parser.LLMError, match="429"):
        parser.parse_request(MESSAGES)
    sleep.assert_not_called()


def test_clarify_contains_all_missing_fields_for_mixed_categories(post):
    post.return_value = success({**INTENT, "budget_rub": None, "categories": ["table", "sofa"]})
    questions = parser.needs_clarify(parser.parse_request(MESSAGES))
    assert {q["field"] for q in questions} == {"categories", "budget_rub"}


def test_normalization_preserves_false_and_zero(post):
    post.return_value = success({**INTENT, "budget_rub": 0, "constraints": {
        "adjustable_height": False, "width_cm": {"min": None, "max": None},
    }})
    result = parser.parse_request(MESSAGES)
    assert result["budget_rub"] == 0
    assert result["constraints"] == {"adjustable_height": False}
