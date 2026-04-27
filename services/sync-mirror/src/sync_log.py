"""Postgres sync_log insertion and health check query.

Uses asyncpg with $N placeholders.  The sync_log schema is:
    id, synced_at, direction, files_updated, files_checked, duration_ms, status, error

There is no 'source', 'files_synced', or 'error_detail' column.
"""

from datetime import UTC, datetime, timedelta

import asyncpg


class SyncLogger:
    """Async sync_log writer backed by an asyncpg connection."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def log_sync(
        self,
        direction: str,
        files_updated: int,
        files_checked: int,
        duration_ms: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """INSERT a sync_log row.

        Args:
            direction: 'inbound' or 'outbound'.
            files_updated: Number of files written/changed.
            files_checked: Number of files examined (superset of files_updated).
            duration_ms: Wall-clock duration of the sync cycle in milliseconds.
            status: Outcome string (e.g. 'success', 'error').
            error: Optional error message on failure.
        """
        sql = (
            "INSERT INTO sync_log"
            " (direction, files_updated, files_checked, duration_ms, status, error)"
            " VALUES ($1, $2, $3, $4, $5, $6)"
        )
        await self._conn.execute(sql, direction, files_updated, files_checked, duration_ms, status, error)

    async def check_health(self, max_age_minutes: int = 20) -> bool:
        """Return True if the last successful inbound sync is within max_age_minutes."""
        sql = (
            "SELECT synced_at FROM sync_log"
            " WHERE direction = 'inbound' AND status = 'success'"
            " ORDER BY synced_at DESC LIMIT 1"
        )
        row = await self._conn.fetchrow(sql)
        if row is None:
            return False
        last_sync: datetime = row["synced_at"]
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=UTC)
        threshold = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
        return last_sync >= threshold
