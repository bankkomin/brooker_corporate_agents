"""Unit tests for synthesise_response node."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from services.cac_orchestrator.src.nodes.synthesise import synthesise_response


@pytest.fixture
def llm_client() -> AsyncMock:
    client = AsyncMock()
    client.chat = AsyncMock(return_value="Here is the synthesised answer.")
    return client


def _base_state(**kwargs: object) -> dict:
    base: dict = {
        "query": "What is the LCR ratio?",
        "context_text": "[1] alco.pdf p.3: LCR is 1.15",
        "agent_response": "Based on the document, LCR is 1.15.",
        "confidence_score": 0.88,
        "escalation_triggered": False,
        "escalation_detail": None,
        "excel_nav": None,
        "staging_proposal_id": None,
        "validation_warnings": [],
    }
    base.update(kwargs)
    return base


async def test_includes_citations_in_prompt(llm_client: AsyncMock) -> None:
    """context_text from state is included in the LLM user prompt."""
    state = _base_state(context_text="[1] report.pdf p.1: key fact")
    await synthesise_response(state, llm_client=llm_client)
    call_args = llm_client.chat.call_args
    messages = call_args[0][0]
    user_content = messages[1]["content"]
    assert "[1] report.pdf p.1: key fact" in user_content


async def test_maps_high_confidence(llm_client: AsyncMock) -> None:
    """score=0.90 maps to 'High'."""
    result = await synthesise_response(_base_state(confidence_score=0.90), llm_client=llm_client)
    assert result["confidence"] == "High"


async def test_maps_medium_confidence(llm_client: AsyncMock) -> None:
    """score=0.70 maps to 'Medium'."""
    result = await synthesise_response(_base_state(confidence_score=0.70), llm_client=llm_client)
    assert result["confidence"] == "Medium"


async def test_maps_low_confidence(llm_client: AsyncMock) -> None:
    """score=0.40 maps to 'Low'."""
    result = await synthesise_response(_base_state(confidence_score=0.40), llm_client=llm_client)
    assert result["confidence"] == "Low"


async def test_handles_empty_sources(llm_client: AsyncMock) -> None:
    """No context_text results in 'No relevant documents found' in the prompt."""
    state = _base_state(context_text="")
    await synthesise_response(state, llm_client=llm_client)
    call_args = llm_client.chat.call_args
    messages = call_args[0][0]
    user_content = messages[1]["content"]
    assert "No relevant documents" in user_content


async def test_llm_error_returns_safe_message(llm_client: AsyncMock) -> None:
    """When LLM raises an exception, a safe fallback answer is returned."""
    llm_client.chat.side_effect = RuntimeError("vLLM unavailable")
    result = await synthesise_response(_base_state(), llm_client=llm_client)
    assert "error" in result["answer"].lower() or "try again" in result["answer"].lower()
    # confidence label is still computed from score
    assert result["confidence"] == "High"
