"""Unit tests for DBClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from services.cac_orchestrator.src.tools.db_client import DBClient


@pytest.fixture
def mock_pool() -> MagicMock:
    pool = MagicMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock()
    return pool


@pytest.mark.asyncio
async def test_log_interaction_with_pool(mock_pool: MagicMock) -> None:
    """Verify SQL params are passed correctly and row ID is returned."""
    mock_pool.fetchrow.return_value = {"id": 99}
    client = DBClient(pool=mock_pool)

    result = await client.log_interaction(
        user_id="U123",
        channel="C-alco",
        thread_ts="1711900000.000100",
        query="What is the LCR?",
        intent="query_lcr",
        response="The LCR is 1.12.",
        sources_count=3,
        escalation=False,
        staging_proposal_id="chg_0001",
        confidence=0.91,
        processing_ms=250,
        paperclip_ticket_id=None,
    )

    assert result == 99
    mock_pool.fetchrow.assert_called_once()
    call_args = mock_pool.fetchrow.call_args[0]
    # First arg is SQL, then params
    assert "INSERT INTO agent_interactions" in call_args[0]
    assert "U123" in call_args
    assert "C-alco" in call_args
    assert "What is the LCR?" in call_args


@pytest.mark.asyncio
async def test_log_interaction_without_pool_returns_none() -> None:
    """Pool=None returns None without error."""
    client = DBClient(pool=None)
    result = await client.log_interaction(
        user_id="U123",
        channel="C-alco",
        thread_ts=None,
        query="test",
    )
    assert result is None


@pytest.mark.asyncio
async def test_log_proposal_with_pool(mock_pool: MagicMock) -> None:
    """Verify proposal SQL params are passed correctly."""
    client = DBClient(pool=mock_pool)

    await client.log_proposal(
        proposal_id="chg_0001",
        agent="alco_agent",
        file="alco_tracker.xlsx",
        tab="Liquidity",
        cell="B12",
        old_value="1.05",
        new_value="1.12",
        source="alco_tracker_2025.xlsx",
        confidence=0.91,
        reasoning="Source document explicitly states the updated LCR ratio.",
        interaction_id=99,
    )

    mock_pool.execute.assert_called_once()
    call_args = mock_pool.execute.call_args[0]
    assert "INSERT INTO staging_proposals" in call_args[0]
    assert "chg_0001" in call_args
    assert "alco_agent" in call_args
    assert "alco_tracker.xlsx" in call_args
    assert "B12" in call_args
    assert "1.12" in call_args


@pytest.mark.asyncio
async def test_log_proposal_without_pool_noop() -> None:
    """Pool=None logs a warning and returns without error."""
    client = DBClient(pool=None)
    # Should not raise
    await client.log_proposal(
        proposal_id="chg_0001",
        agent="alco_agent",
        file="alco_tracker.xlsx",
        tab="Liquidity",
        cell="B12",
        old_value="1.05",
        new_value="1.12",
        source="alco_tracker_2025.xlsx",
        confidence=0.91,
        reasoning="Test reasoning",
    )


@pytest.mark.asyncio
async def test_log_escalation_with_pool(mock_pool: MagicMock) -> None:
    """Verify escalation SQL params are passed correctly."""
    client = DBClient(pool=mock_pool)

    await client.log_escalation(
        interaction_id=99,
        severity="high",
        trigger_type="confidence_below_threshold",
        detail="Confidence 0.45 < 0.70 threshold",
        paperclip_ticket_id="TKT-123",
    )

    mock_pool.execute.assert_called_once()
    call_args = mock_pool.execute.call_args[0]
    assert "INSERT INTO escalations" in call_args[0]
    assert 99 in call_args
    assert "high" in call_args
    assert "confidence_below_threshold" in call_args
    assert "TKT-123" in call_args


@pytest.mark.asyncio
async def test_create_interaction_returns_id() -> None:
    mock_pool = AsyncMock()
    mock_pool.fetchrow.return_value = {"id": 42}
    client = DBClient(pool=mock_pool)
    result = await client.create_interaction(
        user_id="U123", channel="C-test", thread_ts="123.456", query="test query"
    )
    assert result == 42
    mock_pool.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_create_interaction_no_pool() -> None:
    client = DBClient(pool=None)
    result = await client.create_interaction(
        user_id="U123", channel="C-test", thread_ts=None, query="test"
    )
    assert result is None


@pytest.mark.asyncio
async def test_update_interaction() -> None:
    mock_pool = AsyncMock()
    client = DBClient(pool=mock_pool)
    await client.update_interaction(
        interaction_id=42, intent="liquidity", response="Analysis...",
        sources_count=3, escalation=False, staging_proposal_id=None,
        confidence=0.88, processing_ms=1500, paperclip_ticket_id=None,
    )
    mock_pool.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_interaction_skips_none_id() -> None:
    mock_pool = AsyncMock()
    client = DBClient(pool=mock_pool)
    await client.update_interaction(interaction_id=None)
    mock_pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_recent_proposals_for_cell(mock_pool: MagicMock) -> None:
    """Verify returns list of dicts from pool.fetch rows."""
    row1 = MagicMock()
    row1.__iter__ = MagicMock(
        return_value=iter(
            [
                ("id", "chg_0001"),
                ("created_at", "2025-11-01T10:30:00Z"),
                ("agent", "alco_agent"),
                ("old_value", "1.05"),
                ("new_value", "1.12"),
                ("confidence", 0.91),
                ("reasoning", "Source says so"),
                ("status", "pending"),
            ]
        )
    )
    # Use a real dict instead of mock for easier dict() conversion
    row_dict = {
        "id": "chg_0001",
        "created_at": "2025-11-01T10:30:00Z",
        "agent": "alco_agent",
        "old_value": "1.05",
        "new_value": "1.12",
        "confidence": 0.91,
        "reasoning": "Source says so",
        "status": "pending",
    }
    mock_pool.fetch.return_value = [row_dict]

    client = DBClient(pool=mock_pool)
    results = await client.get_recent_proposals_for_cell(
        file="alco_tracker.xlsx", tab="Liquidity", cell="B12", days=7
    )

    assert len(results) == 1
    assert results[0]["id"] == "chg_0001"
    assert results[0]["agent"] == "alco_agent"

    mock_pool.fetch.assert_called_once()
    call_args = mock_pool.fetch.call_args[0]
    assert "staging_proposals" in call_args[0]
    assert "alco_tracker.xlsx" in call_args
    assert "B12" in call_args
    assert 7 in call_args
