"""Unit tests for services/shared/vault_staging.py"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.shared.vault_staging import (
    VaultStagingManifest,
    build_manifest,
    write_vault_staging,
)


def test_build_manifest_fills_id_and_timestamp():
    m = build_manifest(
        agent="meeting-extractor-entities",
        dept="cac",
        target_vault_path="cac/entities/bicl.md",
        operation="update",
        draft_content="# BICL\n\nUpdated content.",
        confidence=0.82,
        reasoning="meeting note added covenant data",
    )
    assert m.id.startswith("chg_")
    assert len(m.id) == 12  # "chg_" + 8 hex
    assert m.created_at.endswith("+00:00")
    assert m.proposal_source == "vault_automation"


def test_manifest_rejects_invalid_confidence():
    with pytest.raises(Exception):
        VaultStagingManifest(
            id="chg_test1234",
            created_at="2026-05-26T00:00:00+00:00",
            agent="x", dept="cac",
            target_vault_path="cac/x.md", operation="create",
            draft_content="x", confidence=1.5, reasoning="r",
        )


def test_manifest_rejects_invalid_operation():
    with pytest.raises(Exception):
        VaultStagingManifest(
            id="chg_test1234",
            created_at="2026-05-26T00:00:00+00:00",
            agent="x", dept="cac",
            target_vault_path="cac/x.md", operation="delete",  # not allowed
            draft_content="x", confidence=0.5, reasoning="r",
        )


@pytest.mark.asyncio
async def test_write_vault_staging_creates_manifest_and_draft(tmp_path: Path):
    staging = tmp_path / "staging"
    m = build_manifest(
        agent="synthesis-proposer",
        dept="regulations",
        target_vault_path="regulations/concepts/audit-committee.md",
        operation="create",
        draft_content="---\ntype: concept\n---\n# Audit Committee\n",
        confidence=0.91,
        reasoning="4 source docs reference audit committee composition",
        synthesis_evidence={
            "entity": "audit-committee",
            "source_count": 4,
            "threshold_used": 3,
        },
    )
    proposal_id = await write_vault_staging(m, staging_path=str(staging))
    assert proposal_id == m.id

    proposal_dir = staging / "pending" / proposal_id
    assert (proposal_dir / "manifest.json").is_file()
    assert (proposal_dir / "draft.md").is_file()

    persisted = json.loads((proposal_dir / "manifest.json").read_text(encoding="utf-8"))
    assert persisted["target_vault_path"] == "regulations/concepts/audit-committee.md"
    assert persisted["operation"] == "create"
    assert persisted["synthesis_evidence"]["source_count"] == 4
    assert persisted["proposal_source"] == "vault_automation"

    draft = (proposal_dir / "draft.md").read_text(encoding="utf-8")
    assert "Audit Committee" in draft


@pytest.mark.asyncio
async def test_write_vault_staging_distinct_ids_for_same_target(tmp_path: Path):
    """Two manifests for the same target_vault_path get distinct proposal ids."""
    staging = tmp_path / "staging"
    args = dict(
        agent="x", dept="cac",
        target_vault_path="cac/decisions/2026-05-26-foo.md",
        operation="create", draft_content="x", confidence=0.7, reasoning="r",
    )
    m1 = build_manifest(**args)
    m2 = build_manifest(**args)
    assert m1.id != m2.id
    id1 = await write_vault_staging(m1, staging_path=str(staging))
    id2 = await write_vault_staging(m2, staging_path=str(staging))
    assert id1 != id2
    assert (staging / "pending" / id1 / "manifest.json").is_file()
    assert (staging / "pending" / id2 / "manifest.json").is_file()
