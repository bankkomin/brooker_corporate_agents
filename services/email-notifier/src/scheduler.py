"""APScheduler job for 24h overdue proposal reminders."""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import asyncpg
import structlog

from .email_sender import send_reminder
from .jwt_generator import generate_proposal_token

logger = structlog.get_logger("email-notifier.scheduler")


async def check_overdue_proposals(
    pool: asyncpg.Pool,
    resolve_hod_email: Callable[[str], str | None],
) -> int:
    """Check for proposals pending > 24h and send reminders.

    Avoids duplicate reminders: checks email_log for any 'reminder' event
    sent to the same proposal today.

    Args:
        pool: asyncpg connection pool.
        resolve_hod_email: Function to resolve HOD email from dept.

    Returns:
        Number of reminders sent.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(hours=24)
    today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    async with pool.acquire() as conn:
        # Find proposals pending > 24h
        overdue = await conn.fetch(
            """
            SELECT proposal_id, dept
            FROM staging_proposals
            WHERE status = 'pending'
              AND created_at < $1
            ORDER BY created_at ASC
            """,
            cutoff,
        )

        if not overdue:
            logger.info("scheduler.no_overdue_proposals")
            return 0

        # Check which proposals already got a reminder today
        proposal_ids = [r["proposal_id"] for r in overdue]
        already_reminded = await conn.fetch(
            """
            SELECT DISTINCT proposal_id
            FROM email_log
            WHERE event_type = 'reminder'
              AND proposal_id = ANY($1::text[])
              AND sent_at >= $2
            """,
            proposal_ids,
            today_start,
        )

    reminded_set = {r["proposal_id"] for r in already_reminded}
    sent = 0

    for row in overdue:
        pid = row["proposal_id"]
        dept = row["dept"]

        if pid in reminded_set:
            logger.debug("scheduler.already_reminded_today", proposal_id=pid)
            continue

        hod_email = resolve_hod_email(dept)
        if not hod_email:
            logger.warning("scheduler.no_hod_email", dept=dept, proposal_id=pid)
            continue

        token = generate_proposal_token(
            proposal_id=pid,
            dept=dept,
            hod_email=hod_email,
        )

        await send_reminder(
            proposal_id=pid,
            recipient=hod_email,
            token=token,
            pool=pool,
        )

        logger.info("scheduler.reminder_sent", proposal_id=pid, dept=dept, recipient=hod_email)
        sent += 1

    logger.info("scheduler.done", total_overdue=len(overdue), reminders_sent=sent)
    return sent
