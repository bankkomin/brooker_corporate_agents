"""Unit tests for staging_writer node."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from services.cac_orchestrator.src.nodes.staging_writer import staging_writer


@pytest.fixture
def db_client() -> AsyncMock:
    client = AsyncMock()
    client.log_proposal = AsyncMock()
    return client


def _base_state(**kwargs: object) -> dict:
    base: dict = {
        "proposed_value": "3.5",
        "proposed_cell": "E8",
        "confidence_score": 0.92,
        "agent_name": "alco_agent",
        "user_id": "U123",
        "channel": "C-alco",
        "tab": "Funding Facilities",
        "old_value": "3.2",
        "context_text": "Covenant threshold is 3.5",
        "agent_response": "Updated based on Q4 report",
        "paperclip_ticket_id": "PPC-0001",
    }
    base.update(kwargs)
    return base


async def test_writes_valid_manifest_json(tmp_path: Path, db_client: AsyncMock) -> None:
    """A manifest.json is created under pending/{id}/."""
    result = await staging_writer(
        _base_state(), db_client=db_client, staging_path=str(tmp_path)
    )
    proposal_id = result["staging_proposal_id"]
    assert proposal_id is not None
    manifest_file = tmp_path / "pending" / proposal_id / "manifest.json"
    assert manifest_file.exists()
    data = json.loads(manifest_file.read_text())
    assert data["id"] == proposal_id


async def test_manifest_has_all_prd_fields(tmp_path: Path, db_client: AsyncMock) -> None:
    """All 16 ManifestProposal fields are present in the written JSON."""
    result = await staging_writer(_base_state(), db_client=db_client, staging_path=str(tmp_path))
    proposal_id = result["staging_proposal_id"]
    manifest_file = tmp_path / "pending" / proposal_id / "manifest.json"
    data = json.loads(manifest_file.read_text())
    required_fields = [
        "id", "created_at", "agent", "triggered_by", "slack_user",
        "file", "tab", "cell", "old_value", "new_value", "source",
        "source_excerpt", "confidence", "reasoning", "status", "paperclip_ticket_id",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


async def test_creates_directory_structure(tmp_path: Path, db_client: AsyncMock) -> None:
    """The pending/{id}/ directory is created."""
    result = await staging_writer(_base_state(), db_client=db_client, staging_path=str(tmp_path))
    proposal_id = result["staging_proposal_id"]
    proposal_dir = tmp_path / "pending" / proposal_id
    assert proposal_dir.is_dir()


async def test_skips_when_confidence_below_threshold(tmp_path: Path, db_client: AsyncMock) -> None:
    """confidence_score below threshold returns None without writing files."""
    result = await staging_writer(
        _base_state(confidence_score=0.80),
        db_client=db_client,
        staging_path=str(tmp_path),
        confidence_threshold=0.85,
    )
    assert result["staging_proposal_id"] is None
    assert not (tmp_path / "pending").exists()


async def test_skips_when_no_proposed_value(tmp_path: Path, db_client: AsyncMock) -> None:
    """No proposed_value returns None without writing files."""
    state = _base_state()
    state["proposed_value"] = None
    result = await staging_writer(state, db_client=db_client, staging_path=str(tmp_path))
    assert result["staging_proposal_id"] is None


async def test_proposal_id_format(tmp_path: Path, db_client: AsyncMock) -> None:
    """proposal_id starts with 'chg_' and has an 8-char hex suffix."""
    result = await staging_writer(_base_state(), db_client=db_client, staging_path=str(tmp_path))
    pid = result["staging_proposal_id"]
    assert pid is not None
    assert pid.startswith("chg_")
    suffix = pid[4:]
    assert len(suffix) == 8
    assert all(c in "0123456789abcdef" for c in suffix)


async def test_handles_directory_creation_failure(tmp_path: Path, db_client: AsyncMock) -> None:
    """OSError during makedirs returns None gracefully."""
    with patch("services.cac_orchestrator.src.nodes.staging_writer.os.makedirs") as mock_mkdir:
        mock_mkdir.side_effect = OSError("permission denied")
        result = await staging_writer(
            _base_state(), db_client=db_client, staging_path=str(tmp_path)
        )
    assert result["staging_proposal_id"] is None


async def test_logs_to_postgres(tmp_path: Path, db_client: AsyncMock) -> None:
    """db_client.log_proposal is called with the correct proposal_id."""
    result = await staging_writer(_base_state(), db_client=db_client, staging_path=str(tmp_path))
    db_client.log_proposal.assert_awaited_once()
    call_kwargs = db_client.log_proposal.call_args[1]
    assert call_kwargs["proposal_id"] == result["staging_proposal_id"]
    assert call_kwargs["agent"] == "alco_agent"
