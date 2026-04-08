"""Email delivery logging to Postgres email_log table."""
from __future__ import annotations

import asyncpg
import structlog

logger = structlog.get_logger("email-notifier.db_logger")


async def log_email_attempt(
    pool: asyncpg.Pool,
    *,
    recipient: str,
    event_type: str,
    proposal_id: str | None = None,
    dept: str | None = None,
    subject: str,
    status: str = "pending",
    error: str | None = None,
    retry_count: int = 0,
) -> int:
    """Insert a row into email_log and return the row id.

    Args:
        pool: Active asyncpg connection pool.
        recipient: Destination email address.
        event_type: Category of email (e.g. "proposal", "reminder", "confirmed").
        proposal_id: Optional change-proposal identifier.
        dept: Optional department code.
        subject: Email subject line.
        status: Initial delivery status — defaults to "pending".
        error: Optional error message if already failed.
        retry_count: Number of attempts already made — defaults to 0.

    Returns:
        The auto-generated integer id of the inserted row.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO email_log
                (recipient, event_type, proposal_id, dept,
                 subject, delivery_status, error, retry_count)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            recipient,
            event_type,
            proposal_id,
            dept,
            subject,
            status,
            error,
            retry_count,
        )
    log_id: int = row["id"]
    logger.info(
        "email_log.inserted",
        log_id=log_id,
        recipient=recipient,
        event_type=event_type,
        status=status,
    )
    return log_id


async def update_email_status(
    pool: asyncpg.Pool,
    log_id: int,
    *,
    status: str,
    error: str | None = None,
    retry_count: int | None = None,
) -> None:
    """Update delivery_status (and optionally error/retry_count) for an email_log row.

    Args:
        pool: Active asyncpg connection pool.
        log_id: Primary key of the row to update.
        status: New delivery_status value (e.g. "sent", "retrying", "failed").
        error: Optional error message to store.
        retry_count: Optional updated attempt count.
    """
    if retry_count is not None:
        await _execute(
            pool,
            "UPDATE email_log SET delivery_status = $1, error = $2, retry_count = $3 WHERE id = $4",
            status,
            error,
            retry_count,
            log_id,
        )
    else:
        await _execute(
            pool,
            "UPDATE email_log SET delivery_status = $1, error = $2 WHERE id = $3",
            status,
            error,
            log_id,
        )
    logger.info("email_log.updated", log_id=log_id, status=status)


async def _execute(pool: asyncpg.Pool, query: str, *args: object) -> None:
    """Execute a parameterised write query using a pooled connection."""
    async with pool.acquire() as conn:
        await conn.execute(query, *args)
