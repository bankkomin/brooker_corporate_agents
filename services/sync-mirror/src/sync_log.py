"""Postgres sync_log insertion and health check query."""

from datetime import UTC, datetime, timedelta
from typing import Any


class SyncLogger:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def log_sync(
        self,
        direction: str,
        source: str,
        files_synced: int,
        status: str,
        error_detail: str | None = None,
    ) -> None:
        sql = (
            "INSERT INTO sync_log"
            " (direction, source, files_synced, status, error_detail, synced_at)"
            " VALUES (%s, %s, %s, %s, %s, %s)"
        )
        async with self._conn.cursor() as cur:
            await cur.execute(
                sql,
                (direction, source, files_synced, status, error_detail, datetime.now(UTC)),
            )
        await self._conn.commit()

    async def check_health(self, max_age_minutes: int = 20) -> bool:
        sql = (
            "SELECT synced_at FROM sync_log"
            " WHERE direction = 'inbound' AND status = 'success'"
            " ORDER BY synced_at DESC LIMIT 1"
        )
        async with self._conn.cursor() as cur:
            await cur.execute(sql)
            row = await cur.fetchone()
        if row is None:
            return False
        last_sync: datetime = row[0]
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=UTC)
        threshold = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
        return last_sync >= threshold
