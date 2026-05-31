"""Tests for ``nl_translator._extract_json_object`` + ``translate_nl_to_rule``.

Focused on the pure-Python parsing layer (no Ollama call) and on the
retry/error paths via a mock OllamaClient.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.governance.yaml_policy.nl_translator import (
    RuleTranslationError,
    _extract_json_object,
    translate_nl_to_rule,
)


# ---------------------------------------------------------------------------
# _extract_json_object — pure parser
# ---------------------------------------------------------------------------


def test_extract_plain_json():
    assert _extract_json_object('{"x": 1}') == {"x": 1}


def test_extract_strips_markdown_fence_with_lang():
    text = '```json\n{"x": 1}\n```'
    assert _extract_json_object(text) == {"x": 1}


def test_extract_strips_markdown_fence_no_lang():
    text = '```\n{"x": 1}\n```'
    assert _extract_json_object(text) == {"x": 1}


def test_extract_handles_leading_prose():
    text = 'Aqui está o JSON:\n{"x": 1, "y": "abc"}'
    assert _extract_json_object(text) == {"x": 1, "y": "abc"}


def test_extract_handles_trailing_prose():
    text = '{"x": 1, "y": "abc"}\n\nEspero que ajude!'
    assert _extract_json_object(text) == {"x": 1, "y": "abc"}


def test_extract_handles_nested_objects():
    text = '{"outer": {"inner": {"deep": [1, 2, 3]}}, "tail": "x"}'
    assert _extract_json_object(text) == {
        "outer": {"inner": {"deep": [1, 2, 3]}},
        "tail": "x",
    }


def test_extract_handles_braces_inside_strings():
    text = '{"msg": "this { is } not a brace", "n": 42}'
    assert _extract_json_object(text) == {"msg": "this { is } not a brace", "n": 42}


def test_extract_handles_escaped_quotes_in_strings():
    text = r'{"msg": "she said \"hi\"", "n": 1}'
    assert _extract_json_object(text) == {"msg": 'she said "hi"', "n": 1}


def test_extract_raises_on_invalid_json():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _extract_json_object("not json at all")


# ---------------------------------------------------------------------------
# translate_nl_to_rule — full pipeline with mock Ollama
# ---------------------------------------------------------------------------


def _valid_rule_json() -> dict[str, Any]:
    return {
        "id": "test-mold-cycle-rule",
        "description": "Quando molde atingir 850 usos, alertar.",
        "when": {
            "event": "mold_usage_threshold",
            "conditions": [
                {"field": "uses_count", "op": "gte", "value": 850},
            ],
        },
        "then": [
            {
                "action": "alert",
                "params": {
                    "severity": "high",
                    "title": "Molde perto do limite",
                    "message_pt": "Atingiu 850 usos.",
                    "entity_refs": [],
                },
            },
        ],
    }


def _make_mock_ollama(*responses: str) -> AsyncMock:
    """Return a mock client whose .chat() yields given response texts in order."""
    client = AsyncMock()
    client.chat = AsyncMock(
        side_effect=[
            {"message": {"content": text}}
            for text in responses
        ]
    )
    return client


@pytest.mark.asyncio
async def test_translate_happy_path():
    client = _make_mock_ollama(json.dumps(_valid_rule_json()))
    rule = await translate_nl_to_rule(
        "Quando molde atingir 850 usos, alertar.",
        ollama=client, model="test-model",
    )
    assert rule.id == "test-mold-cycle-rule"
    assert rule.when.event.value == "mold_usage_threshold"


@pytest.mark.asyncio
async def test_translate_accepts_pre_parsed_dict_q117f():
    """Q.117.F regressão — OllamaClient.chat(format='json') devolve o JSON
    JÁ parseado (dict), não o envelope {"message":{"content":...}}. O
    translator tem de aceitar essa forma, senão dá sempre 'empty response'
    (bug que só aparecia live, nunca nos testes que mockam o envelope)."""
    client = AsyncMock()
    # Devolve o dict parseado directamente — o contrato real do client.
    client.chat = AsyncMock(return_value=_valid_rule_json())
    rule = await translate_nl_to_rule(
        "Quando molde atingir 850 usos, alertar.",
        ollama=client, model="test-model", max_retries=0,
    )
    assert rule.id == "test-mold-cycle-rule"
    assert rule.when.event.value == "mold_usage_threshold"


@pytest.mark.asyncio
async def test_translate_empty_input_raises():
    with pytest.raises(RuleTranslationError, match="empty"):
        await translate_nl_to_rule("   ")


@pytest.mark.asyncio
async def test_translate_handles_markdown_fenced_response():
    fenced = "```json\n" + json.dumps(_valid_rule_json()) + "\n```"
    client = _make_mock_ollama(fenced)
    rule = await translate_nl_to_rule("x", ollama=client, model="m", max_retries=0)
    assert rule.id == "test-mold-cycle-rule"


@pytest.mark.asyncio
async def test_translate_retries_on_invalid_json():
    invalid = "not json"
    valid = json.dumps(_valid_rule_json())
    client = _make_mock_ollama(invalid, valid)
    rule = await translate_nl_to_rule("x", ollama=client, model="m", max_retries=1)
    assert rule.id == "test-mold-cycle-rule"
    assert client.chat.await_count == 2


@pytest.mark.asyncio
async def test_translate_retries_on_validation_error():
    bad = _valid_rule_json()
    bad["when"]["conditions"][0]["field"] = "not_a_real_field"
    invalid_first = json.dumps(bad)
    valid = json.dumps(_valid_rule_json())
    client = _make_mock_ollama(invalid_first, valid)
    rule = await translate_nl_to_rule("x", ollama=client, model="m", max_retries=1)
    assert rule.id == "test-mold-cycle-rule"
    assert client.chat.await_count == 2


@pytest.mark.asyncio
async def test_translate_exhausts_retries_then_raises():
    invalid = "not json"
    client = _make_mock_ollama(invalid, invalid)
    with pytest.raises(RuleTranslationError, match="valid JSON"):
        await translate_nl_to_rule("x", ollama=client, model="m", max_retries=1)


@pytest.mark.asyncio
async def test_translate_llm_self_refusal_surfaces_as_error():
    refusal = json.dumps({"error": "Não consigo expressar essa regra com este schema"})
    client = _make_mock_ollama(refusal)
    with pytest.raises(RuleTranslationError, match="LLM refused"):
        await translate_nl_to_rule("x", ollama=client, model="m")


@pytest.mark.asyncio
async def test_translate_propagates_ollama_failure():
    client = AsyncMock()
    client.chat = AsyncMock(side_effect=ConnectionError("ollama down"))
    with pytest.raises(RuleTranslationError, match="Ollama call failed"):
        await translate_nl_to_rule("x", ollama=client, model="m")


@pytest.mark.asyncio
async def test_translate_status_default_is_proposed():
    client = _make_mock_ollama(json.dumps(_valid_rule_json()))
    rule = await translate_nl_to_rule("x", ollama=client, model="m")
    # Default status from Pydantic is PROPOSED — the LLM doesn't set it.
    assert rule.status.value == "proposed"
