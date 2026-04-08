"""Unit tests for classify_intent node."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from services.cac_orchestrator.src.nodes.classify_intent import classify_intent


@pytest.fixture
def llm_client() -> AsyncMock:
    client = AsyncMock()
    client.chat = AsyncMock()
    return client


async def test_classify_liquidity_intent(llm_client: AsyncMock) -> None:
    """LLM returns liquidity intent — result matches."""
    llm_client.chat.return_value = json.dumps({"intent": "liquidity", "confidence": 0.95})
    state = {"query": "What is the LCR ratio?"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "liquidity"
    assert result["intent_confidence"] == 0.95


async def test_classify_capital_intent(llm_client: AsyncMock) -> None:
    """LLM returns capital intent — result matches."""
    llm_client.chat.return_value = json.dumps({"intent": "capital", "confidence": 0.88})
    state = {"query": "What is our CET1 ratio?"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "capital"
    assert result["intent_confidence"] == 0.88


async def test_classify_alm_intent(llm_client: AsyncMock) -> None:
    """LLM returns alm intent — result matches."""
    llm_client.chat.return_value = json.dumps({"intent": "alm", "confidence": 0.91})
    state = {"query": "What is the duration gap?"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "alm"
    assert result["intent_confidence"] == 0.91


async def test_classify_funding_intent(llm_client: AsyncMock) -> None:
    """LLM returns funding intent — result matches."""
    llm_client.chat.return_value = json.dumps({"intent": "funding", "confidence": 0.78})
    state = {"query": "How much is drawn on the SCB facility?"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "funding"
    assert result["intent_confidence"] == 0.78


async def test_classify_general_intent(llm_client: AsyncMock) -> None:
    """LLM returns general intent — result matches."""
    llm_client.chat.return_value = json.dumps({"intent": "general", "confidence": 0.60})
    state = {"query": "What happened at the last ALCO meeting?"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "general"
    assert result["intent_confidence"] == 0.60


async def test_classify_unknown_intent_falls_back(llm_client: AsyncMock) -> None:
    """LLM returns unrecognised category — falls back to 'general'."""
    llm_client.chat.return_value = json.dumps({"intent": "unknown_category", "confidence": 0.70})
    state = {"query": "some query"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "general"


async def test_classify_confidence_between_0_and_1(llm_client: AsyncMock) -> None:
    """Confidence is clamped to [0.0, 1.0]."""
    llm_client.chat.return_value = json.dumps({"intent": "liquidity", "confidence": 1.5})
    state = {"query": "test"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent_confidence"] == 1.0

    llm_client.chat.return_value = json.dumps({"intent": "capital", "confidence": -0.3})
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent_confidence"] == 0.0


async def test_classify_malformed_json_falls_back(llm_client: AsyncMock) -> None:
    """LLM returns non-JSON — falls back to intent='general', confidence=0.5."""
    llm_client.chat.return_value = "not json at all"
    state = {"query": "test query"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "general"
    assert result["intent_confidence"] == 0.5


async def test_classify_missing_fields_falls_back(llm_client: AsyncMock) -> None:
    """LLM returns empty JSON object — defaults applied."""
    llm_client.chat.return_value = json.dumps({})
    state = {"query": "test"}
    result = await classify_intent(state, llm_client=llm_client)
    assert result["intent"] == "general"
    assert result["intent_confidence"] == 0.5


async def test_classify_sends_correct_messages(llm_client: AsyncMock) -> None:
    """LLM must receive a system prompt and the user query."""
    llm_client.chat.return_value = json.dumps({"intent": "alm", "confidence": 0.80})
    state = {"query": "What is the NSFR?"}
    await classify_intent(state, llm_client=llm_client)

    llm_client.chat.assert_awaited_once()
    call_args = llm_client.chat.call_args
    messages = call_args[0][0]  # positional first arg
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "What is the NSFR?"
