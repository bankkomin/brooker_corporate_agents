"""Unit tests for validate_proposal node."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.cac_orchestrator.src.nodes.validate_proposal import validate_proposal
from services.cac_orchestrator.src.tools.db_client import DBClient
from services.cac_orchestrator.src.tools.llm_client import LLMClient


@pytest.fixture
def llm_client() -> AsyncMock:
    client = AsyncMock()
    client.chat = AsyncMock()
    return client


@pytest.fixture
def db_client() -> AsyncMock:
    client = AsyncMock()
    client.get_recent_proposals_for_cell = AsyncMock(return_value=[])
    return client


def _base_state(**kwargs: object) -> dict:
    base: dict = {
        "proposed_value": "3.5",
        "proposed_cell": "E8",
        "confidence_score": 0.90,
        "agent_response": "Source states covenant threshold is 3.5",
        "context_text": "Covenant threshold is 3.5 per ALCO policy doc",
        "old_value": "3.2",
        "excel_nav": "ALCO_Tracker.xlsx → Tab: Funding Facilities → Row 8 → Column E",
    }
    base.update(kwargs)
    return base


async def test_passes_when_source_correct(llm_client: AsyncMock, db_client: AsyncMock) -> None:
    """LLM confirms proposal — passed=True, no warnings."""
    llm_client.chat.return_value = json.dumps(
        {"passed": True, "confidence_adjustment": 0.0, "warnings": [], "blocking_reason": None}
    )
    result = await validate_proposal(_base_state(), llm_client=llm_client, db_client=db_client)
    assert result["validation_passed"] is True
    assert result["validation_warnings"] == []
    assert result["confidence_score"] == pytest.approx(0.90)


async def test_fails_when_hallucination_detected(
    llm_client: AsyncMock, db_client: AsyncMock,
) -> None:
    """LLM detects hallucination — passed=False, blocking_reason in warnings."""
    llm_client.chat.return_value = json.dumps(
        {
            "passed": False,
            "confidence_adjustment": 0.0,
            "warnings": [],
            "blocking_reason": "Value not in source",
        }
    )
    result = await validate_proposal(_base_state(), llm_client=llm_client, db_client=db_client)
    assert result["validation_passed"] is False
    assert any("BLOCKED" in w for w in result["validation_warnings"])


async def test_detects_contradiction_with_recent(
    llm_client: AsyncMock, db_client: AsyncMock,
) -> None:
    """When db returns recent proposals, history section appears in LLM prompt."""
    db_client.get_recent_proposals_for_cell.return_value = [
        {
            "created_at": "2025-11-01",
            "agent": "alco_agent",
            "new_value": "3.1",
            "confidence": 0.88,
            "status": "approved",
        }
    ]
    llm_client.chat.return_value = json.dumps(
        {"passed": True, "confidence_adjustment": 0.0, "warnings": [], "blocking_reason": None}
    )
    await validate_proposal(_base_state(), llm_client=llm_client, db_client=db_client)
    call_args = llm_client.chat.call_args
    prompt_text = call_args[0][0][1]["content"]  # user message content
    assert "Recent proposals" in prompt_text


async def test_downgrades_confidence(llm_client: AsyncMock, db_client: AsyncMock) -> None:
    """Negative confidence_adjustment reduces returned confidence_score."""
    llm_client.chat.return_value = json.dumps(
        {"passed": True, "confidence_adjustment": -0.1, "warnings": [], "blocking_reason": None}
    )
    result = await validate_proposal(
        _base_state(confidence_score=0.90), llm_client=llm_client, db_client=db_client
    )
    assert result["confidence_score"] == pytest.approx(0.80)


async def test_no_recent_proposals_graceful(llm_client: AsyncMock, db_client: AsyncMock) -> None:
    """Empty recent proposals list does not break validation."""
    db_client.get_recent_proposals_for_cell.return_value = []
    llm_client.chat.return_value = json.dumps(
        {"passed": True, "confidence_adjustment": 0.0, "warnings": [], "blocking_reason": None}
    )
    result = await validate_proposal(_base_state(), llm_client=llm_client, db_client=db_client)
    assert result["validation_passed"] is True


async def test_warnings_attached(llm_client: AsyncMock, db_client: AsyncMock) -> None:
    """Warnings from LLM are included in result."""
    llm_client.chat.return_value = json.dumps(
        {
            "passed": True,
            "confidence_adjustment": 0.0,
            "warnings": ["minor concern about rounding"],
            "blocking_reason": None,
        }
    )
    result = await validate_proposal(_base_state(), llm_client=llm_client, db_client=db_client)
    assert "minor concern about rounding" in result["validation_warnings"]


async def test_skips_when_no_proposed_value(llm_client: AsyncMock, db_client: AsyncMock) -> None:
    """No proposed_value means validation auto-passes without calling LLM."""
    state = _base_state()
    state.pop("proposed_value")
    result = await validate_proposal(state, llm_client=llm_client, db_client=db_client)
    assert result["validation_passed"] is True
    llm_client.chat.assert_not_awaited()


async def test_skips_when_no_proposed_cell(llm_client: AsyncMock, db_client: AsyncMock) -> None:
    """No proposed_cell means validation auto-passes without calling LLM."""
    state = _base_state()
    state.pop("proposed_cell")
    result = await validate_proposal(state, llm_client=llm_client, db_client=db_client)
    assert result["validation_passed"] is True
    llm_client.chat.assert_not_awaited()


async def test_parse_error_blocks_with_warning(llm_client: AsyncMock, db_client: AsyncMock) -> None:
    """Invalid JSON from LLM causes validation_passed=False (fail-closed) with a BLOCKED warning."""
    llm_client.chat.return_value = "definitely not json"
    result = await validate_proposal(_base_state(), llm_client=llm_client, db_client=db_client)
    assert result["validation_passed"] is False
    assert len(result["validation_warnings"]) > 0
    assert "BLOCKED" in result["validation_warnings"][0]
    assert result["confidence_score"] < 0.90


async def test_history_section_included_in_prompt(
    llm_client: AsyncMock, db_client: AsyncMock,
) -> None:
    """When recent proposals exist, prompt text contains the history section."""
    db_client.get_recent_proposals_for_cell.return_value = [
        {
            "created_at": "2025-12-01",
            "agent": "alco_agent",
            "new_value": "3.4",
            "confidence": 0.91,
            "status": "pending",
        }
    ]
    llm_client.chat.return_value = json.dumps(
        {"passed": True, "confidence_adjustment": 0.0, "warnings": [], "blocking_reason": None}
    )
    await validate_proposal(_base_state(), llm_client=llm_client, db_client=db_client)
    call_args = llm_client.chat.call_args
    prompt_text = call_args[0][0][1]["content"]  # user message content
    assert "3.4" in prompt_text  # the recent proposed value must appear


@pytest.mark.asyncio
async def test_validate_blocks_on_parse_error() -> None:
    """Validation must BLOCK (not pass) when LLM returns unparseable response."""
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat = AsyncMock(return_value="This is not valid JSON at all")
    mock_db = MagicMock(spec=DBClient)
    mock_db.get_recent_proposals_for_cell = AsyncMock(return_value=[])

    state = {
        "proposed_value": "1.18",
        "proposed_cell": "D10",
        "confidence_score": 0.90,
        "agent_response": "test",
        "context_text": "test context",
        "excel_nav": "",
    }

    result = await validate_proposal(state, llm_client=mock_llm, db_client=mock_db)
    assert result["validation_passed"] is False
    assert any("BLOCKED" in w for w in result["validation_warnings"])
    assert result["confidence_score"] < 0.90
