"""Shared vault-write staging writer.

The existing `cac-orchestrator/src/nodes/staging_writer.py` writes Excel
cell-change manifests (ALCO_Tracker.xlsx + tab + cell). Vault writes —
new concept notes, new daily-log entries, new entities, new decision
drafts — need a different schema.

This module provides a single async writer used by:

- **B3** (cac-orchestrator post-meeting fan-out) — proposes entities,
  decisions, trends, index updates extracted from a meeting note.
- **B4** (rag-ingestion synthesis_proposer) — proposes new concept
  notes when an entity appears in N+ source documents.
- **B5** (reflection-engine daily-log promotion) — proposes daily-log
  summary entries and per-agent memory updates.

Hard rule (matches CLAUDE.md Data Safety Rule): nothing in this
module writes outside /data/staging/pending/. All vault file writes
require human approval via approval-ui before sync-back applies them
to the real vault.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Literal

import aiofiles
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger("shared.vault_staging")

ProposalSource = Literal["agent", "human", "vault_automation"]
VaultOperation = Literal["create", "update", "append"]


class VaultStagingManifest(BaseModel):
    """Staged vault file proposal — what should be written to obsidian-vault.

    Distinct from `ManifestProposal` (which is for Excel cell changes).
    Both flow through /data/staging/pending/ and approval-ui, but they
    have different targets and different review semantics.
    """

    id: str  # "chg_XXXX"
    created_at: str  # ISO 8601 UTC
    agent: str  # producing agent / subagent name
    proposal_source: ProposalSource = "vault_automation"
    dept: str
    target_vault_path: str  # vault-relative, e.g. "cac/entities/bicl.md"
    operation: VaultOperation
    draft_content: str  # the full file content (operation=create/update) or appended block (operation=append)
    extracted_from: str | None = None  # source meeting-note / document path
    source_run_id: str | None = None  # joins multiple manifests from one fan-out
    synthesis_evidence: dict | None = None  # B4: {entity, source_count, sources, threshold_used}
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    status: str = "pending"


def _next_proposal_id() -> str:
    return f"chg_{uuid.uuid4().hex[:8]}"


async def write_vault_staging(
    manifest: VaultStagingManifest,
    *,
    staging_path: str,
) -> str | None:
    """Persist a vault staging manifest. Returns proposal id, or None on failure.

    Idempotency: caller is responsible for dedup. If two fan-out workers
    propose the same target_vault_path within one source_run_id, they will
    each get distinct proposal ids — the approval-UI is responsible for
    grouping them so the HOD doesn't review duplicates.
    """
    proposal_dir = os.path.join(staging_path, "pending", manifest.id)
    try:
        os.makedirs(proposal_dir, exist_ok=True)
        manifest_path = os.path.join(proposal_dir, "manifest.json")
        async with aiofiles.open(manifest_path, mode="w", encoding="utf-8") as fh:
            await fh.write(manifest.model_dump_json(indent=2))
        # Also write the draft content as a sibling file so the approval-UI
        # can diff against the current vault state without re-parsing JSON.
        content_path = os.path.join(proposal_dir, "draft.md")
        async with aiofiles.open(content_path, mode="w", encoding="utf-8") as fh:
            await fh.write(manifest.draft_content)
    except OSError as exc:
        logger.error(
            "vault_staging.write_failed",
            id=manifest.id,
            target=manifest.target_vault_path,
            error=str(exc),
        )
        return None

    logger.info(
        "vault_staging.written",
        id=manifest.id,
        target=manifest.target_vault_path,
        op=manifest.operation,
        agent=manifest.agent,
        source=manifest.proposal_source,
        confidence=manifest.confidence,
    )
    return manifest.id


def build_manifest(
    *,
    agent: str,
    dept: str,
    target_vault_path: str,
    operation: VaultOperation,
    draft_content: str,
    confidence: float,
    reasoning: str,
    proposal_source: ProposalSource = "vault_automation",
    extracted_from: str | None = None,
    source_run_id: str | None = None,
    synthesis_evidence: dict | None = None,
) -> VaultStagingManifest:
    """Factory with sensible defaults (id + created_at filled)."""
    return VaultStagingManifest(
        id=_next_proposal_id(),
        created_at=datetime.now(UTC).isoformat(),
        agent=agent,
        proposal_source=proposal_source,
        dept=dept,
        target_vault_path=target_vault_path,
        operation=operation,
        draft_content=draft_content,
        extracted_from=extracted_from,
        source_run_id=source_run_id,
        synthesis_evidence=synthesis_evidence,
        confidence=confidence,
        reasoning=reasoning,
    )
