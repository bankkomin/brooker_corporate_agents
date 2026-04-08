"""Integration test: staging flow — classify -> agent -> validate -> staging."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.cac_orchestrator.src.models import ManifestProposal
from services.cac_orchestrator.src.nodes.staging_writer import staging_writer
from services.cac_orchestrator.src.tools.db_client import DBClient


@pytest.fixture
def staging_dir(tmp_path):
    pending = tmp_path / "pending"
    pending.mkdir()
    return str(tmp_path)


def test_manifest_schema_valid() -> None:
    """Verify ManifestProposal matches expected schema."""
    manifest = ManifestProposal(
        id="chg_0001",
        created_at="2026-03-31T10:00:00Z",
        agent="liquidity-agent",
        triggered_by="app_mention",
        slack_user="U123",
        file="ALCO_Tracker.xlsx",
        tab="Liquidity",
        cell="D10",
        old_value=None,
        new_value="1.185",
        source="Slack #cac | U123",
        source_excerpt="LCR is 118.50%",
        confidence=0.92,
        reasoning="Q1 report confirms LCR at 118.50%",
        status="pending",
    )
    data = json.loads(manifest.model_dump_json())
    assert data["id"] == "chg_0001"
    assert data["status"] == "pending"
    assert data["confidence"] == 0.92
    assert data["tab"] == "Liquidity"


def test_agent_response_parses_proposal() -> None:
    """Verify the LLM JSON response format for an agent with a proposal."""
    response = json.dumps({
        "analysis": "LCR is 118.50% [Source: ALCO_Tracker.xlsx, Liquidity tab]",
        "proposed_change": {
            "value": "1.185",
            "cell": "D10",
            "tab": "Liquidity",
            "reasoning": "Q1 report confirms LCR at 118.50%",
        },
        "confidence": 0.92,
        "escalation_flags": [],
    })
    data = json.loads(response)
    assert data["confidence"] >= 0.85
    assert data["proposed_change"]["cell"] == "D10"
    assert data["proposed_change"]["tab"] == "Liquidity"


@pytest.mark.asyncio
async def test_staging_writer_creates_manifest(staging_dir: str) -> None:
    """Staging writer creates manifest.json when confidence is sufficient."""
    mock_db = MagicMock(spec=DBClient)
    mock_db.log_proposal = AsyncMock()

    state = {
        "confidence_score": 0.92,
        "proposed_value": "1.185",
        "proposed_cell": "D10",
        "proposed_tab": "Liquidity",
        "agent_name": "liquidity-agent",
        "user_id": "U123",
        "channel": "C-cac",
        "agent_response": "LCR is 118.50%",
        "context_text": "LCR is 118.50% per Q1 report",
        "old_value": None,
        "interaction_id": 42,
        "paperclip_ticket_id": None,
    }

    result = await staging_writer(
        state, db_client=mock_db, staging_path=staging_dir, confidence_threshold=0.85
    )

    assert result["staging_proposal_id"] is not None
    proposal_id = result["staging_proposal_id"]

    # Verify file was written
    manifest_path = os.path.join(staging_dir, "pending", proposal_id, "manifest.json")
    assert os.path.exists(manifest_path)

    with open(manifest_path) as f:
        manifest_data = json.load(f)
    assert manifest_data["agent"] == "liquidity-agent"
    assert manifest_data["cell"] == "D10"
    assert manifest_data["tab"] == "Liquidity"
    assert manifest_data["confidence"] == 0.92

    # Verify DB was called with interaction_id
    mock_db.log_proposal.assert_called_once()
    call_kwargs = mock_db.log_proposal.call_args[1]
    assert call_kwargs.get("interaction_id") == 42


@pytest.mark.asyncio
async def test_staging_writer_skips_low_confidence(staging_dir: str) -> None:
    """Staging writer skips proposal when confidence is below threshold."""
    mock_db = MagicMock(spec=DBClient)
    mock_db.log_proposal = AsyncMock()

    state = {
        "confidence_score": 0.60,
        "proposed_value": "1.00",
        "proposed_cell": "D10",
        "agent_name": "liquidity-agent",
    }

    result = await staging_writer(
        state, db_client=mock_db, staging_path=staging_dir, confidence_threshold=0.85
    )

    assert result["staging_proposal_id"] is None
    mock_db.log_proposal.assert_not_called()
