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
            rejected_at,
            rejected_by,
            synced_at,
            dept
        FROM staging_proposals
        WHERE status IN ('synced', 'rejected')
          AND archived_at IS NULL
    """
    params: list[object] = []
    if dept is not None:
        query += "  AND dept = $1\n"
        params.append(dept)
    query += "ORDER BY COALESCE(synced_at, rejected_at) ASC"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    if not rows:
        logger.info("archive_completed.no_pending_proposals")
        return 0

    now = datetime.now(tz=UTC)
    archived = 0

    for row in rows:
        status = row["status"]

        # Determine decision timestamp and actor
        if status == "synced":
            decided_at = row["synced_at"] or now
            decided_by = row["approved_by"]
        else:
            decided_at = row["rejected_at"] or now
            decided_by = row["rejected_by"]

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

        # Mark as archived in the database
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE staging_proposals SET archived_at = $1 WHERE proposal_id = $2",
                now,
                record.proposal_id,
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
