"""Archive completed proposals — move synced/rejected to /data/archive/."""
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import structlog

from .config import ARCHIVE_PATH, STAGING_PATH
from .models import ArchiveRecord

logger = structlog.get_logger(__name__)


async def archive_completed(pool: asyncpg.Pool, dept: str | None = None) -> int:
    """Move synced/rejected proposals from staging to archive.

    Creates {ARCHIVE_PATH}/YYYY/MM/{proposal_id}/ with manifest.json
    and a decision.json for each completed proposal.

    Args:
        pool: asyncpg connection pool.
        dept: Optional department filter. When *None*, processes all departments.

    Returns the count of proposals archived.
    """
    # staging_proposals has no approved_at, approved_by, rejected_at, rejected_by,
    # synced_at, or archived_at columns. Decision metadata lives in approval_decisions.
    # Use a LEFT JOIN so rejected proposals without a matching approval_decisions row
    # are still returned. The PK is staging_proposals.id (not proposal_id).
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
            ad.decided_at,
            ad.decided_by,
            ad.decision      AS ad_decision,
            ad.synced_at     AS decision_synced_at
        FROM staging_proposals sp
        LEFT JOIN approval_decisions ad ON ad.proposal_id = sp.id
        WHERE sp.status IN ('synced', 'rejected')
    """
    params: list[object] = []
    if dept is not None:
        query += "  AND sp.dept = $1\n"
        params.append(dept)
    query += "ORDER BY COALESCE(ad.decided_at, sp.created_at) ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    if not rows:
        logger.info("archive_completed.no_pending_proposals")
        return 0

    now = datetime.now(tz=UTC)
    archived = 0

    for row in rows:
        status = row["status"]

        # Decision timestamp and actor come from approval_decisions via the JOIN.
        # Fall back to now() when the LEFT JOIN found no matching decision row.
        decided_at = row["decided_at"] or now
        decided_by = row["decided_by"]
        decision_synced_at = row["decision_synced_at"]

        record = ArchiveRecord(
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
            decision=status,
            decided_at=decided_at,
            decided_by=decided_by,
            decision_synced_at=decision_synced_at,
            archived_at=now,
        )

        # Build archive path: YYYY/MM/{proposal_id}/
        year = decided_at.strftime("%Y")
        month = decided_at.strftime("%m")
        archive_dir = Path(ARCHIVE_PATH) / year / month / record.proposal_id
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest
        manifest = record.model_dump(mode="json")
        (archive_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        # Write decision summary
        decision_summary = {
            "proposal_id": record.proposal_id,
            "decision": record.decision,
            "decided_at": record.decided_at.isoformat(),
            "decided_by": record.decided_by,
            "archived_at": record.archived_at.isoformat(),
        }
        (archive_dir / "decision.json").write_text(
            json.dumps(decision_summary, indent=2),
            encoding="utf-8",
        )

        # Copy any existing staging files into the archive
        staging_proposal_dir = Path(STAGING_PATH) / "approved" / record.proposal_id
        if staging_proposal_dir.exists():
            for src_file in staging_proposal_dir.iterdir():
                dest = archive_dir / src_file.name
                if not dest.exists():
                    shutil.copy2(src_file, dest)

        # staging_proposals has no archived_at column — there is no such field
        # to update. The archive record is the permanent audit trail in /data/archive/.
        # Log the completion so operators can correlate by proposal_id.
        logger.debug(
            "archive_completed.db_note",
            proposal_id=record.proposal_id,
            note="staging_proposals has no archived_at column; archive is filesystem-only",
        )

        logger.info(
            "archive_completed.archived",
            proposal_id=record.proposal_id,
            dept=row["dept"],
            decision=record.decision,
            path=str(archive_dir),
        )
        archived += 1

    logger.info("archive_completed.done", count=archived)
    return archived
