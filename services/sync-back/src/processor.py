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

    # staging_proposals has no approved_at/approved_by/synced_at columns.
    # Those live in approval_decisions (FK: proposal_id → staging_proposals.id).
    # The staging_proposals PK is `id`, not `proposal_id`.
    query = """
        SELECT
            sp.id            AS proposal_id,
            sp.agent,
            sp.file,
            sp.tab,
            sp.cell,
            sp.old_value,
            sp.new_value,
            sp.source,
            sp.confidence,
            sp.reasoning,
            sp.status,
            sp.dept,
            ad.decided_at    AS approved_at,
            ad.decided_by    AS approved_by,
            ad.synced_at     AS decision_synced_at
        FROM staging_proposals sp
        JOIN approval_decisions ad ON ad.proposal_id = sp.id
        WHERE sp.status = 'approved'
          AND ad.decision IN ('approved', 'edited')
          AND ad.synced_at IS NULL
    """
    params: list[object] = []
    if dept is not None:
        query += "  AND sp.dept = $1\n"
        params.append(dept)
    query += "ORDER BY ad.decided_at ASC"

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
            dept=row["dept"],
            approved_at=row["approved_at"],
            approved_by=row["approved_by"],
            decision_synced_at=row["decision_synced_at"],
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

        # Mark proposal as synced and record timestamp on the decision row.
        # staging_proposals.id is the PK (not proposal_id).
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE staging_proposals SET status = 'synced' WHERE id = $1",
                proposal.proposal_id,
            )
            await conn.execute(
                "UPDATE approval_decisions SET synced_at = NOW() WHERE proposal_id = $1"
                "  AND decision IN ('approved', 'edited') AND synced_at IS NULL",
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
