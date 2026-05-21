"""Staging writer node — writes proposals to /data/staging/pending/."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import aiofiles
import structlog

from ..models import ManifestProposal
from ..tools.db_client import DBClient

try:
    from services.shared.permission_enforcement import ensure_can_write
except ImportError:
    ensure_can_write = None

logger = structlog.get_logger("cac-orchestrator.staging")


def _next_proposal_id() -> str:
    """Generate a collision-resistant proposal ID that survives process restarts."""
    return f"chg_{uuid.uuid4().hex[:8]}"


async def staging_writer(
    state: dict,
    *,
    db_client: DBClient,
    staging_path: str,
    confidence_threshold: float = 0.85,
) -> dict:
    """Write a staging proposal to /data/staging/pending/ if confidence is sufficient.

    Returns {"staging_proposal_id": str | None}.
    """
    confidence_score = state.get("confidence_score", 0.0)

    if confidence_score < confidence_threshold:
        logger.info(
            "staging_skipped_low_confidence",
            confidence=confidence_score,
            threshold=confidence_threshold,
        )
        return {"staging_proposal_id": None}

    if not state.get("proposed_value"):
        logger.info("staging_skipped_no_proposal")
        return {"staging_proposal_id": None}

    # Permission gate — only proceed if the agent's skill declared
    # mode=write_via_staging (audit bug #6). If skill_permissions is missing
    # we now FAIL CLOSED rather than silently allowing the write.
    if ensure_can_write is not None:
        skill_perms = state.get("skill_permissions")
        if not skill_perms:
            logger.warning("staging_blocked_no_skill_perms",
                            agent=state.get("agent_name"))
            return {"staging_proposal_id": None,
                    "staging_error": "no skill permissions declared"}
        try:
            ensure_can_write(skill_perms)
        except Exception as perm_err:
            logger.warning("staging_blocked_by_permission", error=str(perm_err))
            return {"staging_proposal_id": None, "staging_error": str(perm_err)}

    proposal_id = _next_proposal_id()

    manifest = ManifestProposal(
        id=proposal_id,
        created_at=datetime.now(UTC).isoformat(),
        agent=state.get("agent_name", "unknown"),
        triggered_by="app_mention",
        slack_user=state.get("user_id", ""),
        file="ALCO_Tracker.xlsx",
        tab=state.get("proposed_tab", state.get("tab", "")),
        cell=state.get("proposed_cell", ""),
        old_value=state.get("old_value"),
        new_value=state.get("proposed_value", ""),
        source=f"Slack #{state.get('channel', '')} | {state.get('user_id', '')}",
        source_excerpt=state.get("context_text", "")[:200],
        confidence=confidence_score,
        reasoning=state.get("agent_response", "")[:500],
        status="pending",
        paperclip_ticket_id=state.get("paperclip_ticket_id"),
    )

    # Write to filesystem
    proposal_dir = os.path.join(staging_path, "pending", proposal_id)
    try:
        os.makedirs(proposal_dir, exist_ok=True)
        manifest_path = os.path.join(proposal_dir, "manifest.json")
        async with aiofiles.open(manifest_path, mode="w", encoding="utf-8") as f:
            await f.write(manifest.model_dump_json(indent=2))
        logger.info("staging_proposal_written", id=proposal_id, path=manifest_path)
    except OSError as exc:
        logger.error("staging_write_failed", id=proposal_id, error=str(exc))
        return {"staging_proposal_id": None}

    # Log to Postgres
    await db_client.log_proposal(
        proposal_id=proposal_id,
        agent=manifest.agent,
        file=manifest.file,
        tab=manifest.tab,
        cell=manifest.cell,
        old_value=manifest.old_value,
        new_value=manifest.new_value,
        source=manifest.source,
        confidence=manifest.confidence,
        reasoning=manifest.reasoning,
        interaction_id=state.get("interaction_id"),
    )

    return {"staging_proposal_id": proposal_id}
