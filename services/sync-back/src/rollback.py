"""Rollback handler for failed Excel writes — reverts DB status and alerts."""
from __future__ import annotations

import shutil
from pathlib import Path

import asyncpg
import httpx
import structlog

from .config import SLACK_WEBHOOK_URL, STAGING_PATH

logger = structlog.get_logger("sync-back.rollback")


async def handle_failure(
    proposal_id: str,
    pool: asyncpg.Pool,
    error: str,
) -> None:
    """Handle a failed Excel write by reverting state and alerting.

    Steps:
        1. Delete staging/approved/{proposal_id}/ directory (cleanup bad write)
        2. Revert DB status back to 'pending' (so proposal appears for retry)
        3. POST to Slack #escalations webhook with failure details
        4. Log error

    Args:
        proposal_id: The proposal that failed to sync.
        pool: asyncpg connection pool.
        error: Error description.
    """
    # 1. Cleanup staging directory
    staging_dir = Path(STAGING_PATH) / "approved" / proposal_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
        logger.info("rollback.staging_cleaned", proposal_id=proposal_id, path=str(staging_dir))

    # 2. Revert DB status to pending
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE staging_proposals SET status = 'pending', synced_at = NULL "
            "WHERE proposal_id = $1 AND status = 'approved'",
            proposal_id,
        )
    logger.info("rollback.db_reverted", proposal_id=proposal_id)

    # 3. Alert Slack
    await _alert_slack(proposal_id, error)

    logger.error("rollback.complete", proposal_id=proposal_id, error=error)


async def _alert_slack(proposal_id: str, error: str) -> None:
    """POST failure alert to Slack #escalations webhook. Fire-and-forget."""
    if not SLACK_WEBHOOK_URL:
        logger.warning("rollback.no_slack_webhook")
        return

    payload = {
        "text": (
            f":rotating_light: *Sync-Back Write Failure*\n"
            f"*Proposal:* `{proposal_id}`\n"
            f"*Error:* {error}\n"
            f"_Status reverted to pending. Manual intervention may be required._"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
        logger.info("rollback.slack_alerted", proposal_id=proposal_id)
    except Exception as exc:
        logger.error("rollback.slack_failed", error=str(exc))
