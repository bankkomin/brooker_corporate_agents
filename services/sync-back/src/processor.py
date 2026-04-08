"""Process approved proposals — write Excel cells and mark as synced."""
import json
from pathlib import Path

import asyncpg
import structlog

from .config import MIRROR_PATH, STAGING_PATH
from .models import ApprovedProposal
from .notifier_client import notify_confirmed
from .openpyxl_writer import ExcelWriteError, write_cell
from .rollback import handle_failure

logger = structlog.get_logger(__name__)


async def process_approved(pool: asyncpg.Pool, dept: str | None = None) -> int:
    """Query approved proposals, write Excel cells, and mark as synced.

    Steps for each proposal:
        1. Write manifest JSON to staging/approved/{proposal_id}/
        2. Write the cell value to a copy of the Excel file in staging
        3. Mark as synced in DB
        4. Notify email-notifier (fire-and-forget)

    On Excel write failure, handle_failure() is called which:
        - Deletes the staging/approved/{proposal_id}/ directory
        - Reverts DB status to 'pending' for retry
        - Alerts Slack #escalations webhook

    Args:
        pool: asyncpg connection pool.
        dept: Optional department filter. When *None*, processes all departments.

    Returns the count of proposals successfully synced.
    """
    approved_dir = Path(STAGING_PATH) / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)

    query = """
        SELECT
            proposal_id,
            agent,
            file,
            tab,
            cell,
            old_value,
            new_value,
            source,
            confidence,
            reasoning,
            status,
            approved_at,
            approved_by,
            dept
        FROM staging_proposals
        WHERE status = 'approved'
          AND synced_at IS NULL
    """
    params: list[object] = []
    if dept is not None:
        query += "  AND dept = $1\n"
        params.append(dept)
    query += "ORDER BY approved_at ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    if not rows:
        logger.info("process_approved.no_pending_proposals")
        return 0

    processed = 0
    for row in rows:
        proposal = ApprovedProposal(
            proposal_id=row["proposal_id"],
            agent=row["agent"],
            file=row["file"],
            tab=row["tab"],
            cell=row["cell"],
            old_value=row["old_value"],
            new_value=row["new_value"],
            source=row["source"],
            confidence=float(row["confidence"]),
            reasoning=row["reasoning"],
            status=row["status"],
            approved_at=row["approved_at"],
            approved_by=row["approved_by"],
        )

        proposal_dir = approved_dir / proposal.proposal_id
        proposal_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = proposal_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(proposal.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

        logger.info(
            "process_approved.manifest_written",
            proposal_id=proposal.proposal_id,
            dept=row["dept"],
            path=str(manifest_path),
        )

        # Write to Excel copy
        try:
            write_cell(proposal, MIRROR_PATH, STAGING_PATH)
        except (FileNotFoundError, ExcelWriteError) as exc:
            logger.error(
                "process_approved.excel_write_failed",
                proposal_id=proposal.proposal_id,
                error=str(exc),
            )
            await handle_failure(proposal.proposal_id, pool, str(exc))
            continue  # Skip to next proposal

        # Mark as synced in DB
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE staging_proposals SET synced_at = NOW(), status = 'synced' "
                "WHERE proposal_id = $1",
                proposal.proposal_id,
            )

        # Notify email-notifier (fire-and-forget)
        await notify_confirmed(
            proposal_id=proposal.proposal_id,
            decision="approved",
            dept=row["dept"],
        )

        logger.info(
            "process_approved.synced",
            proposal_id=proposal.proposal_id,
            dept=row["dept"],
        )
        processed += 1

    logger.info("process_approved.done", count=processed)
    return processed
