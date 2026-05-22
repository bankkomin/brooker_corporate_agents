"""Tests for Postgres sync_log insertion and health check."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from services.sync_mirror.src.sync_log import SyncLogger


def _make_conn() -> AsyncMock:
    """Build a mock asyncpg connection with async execute/fetchrow methods."""
    conn = AsyncMock()
    return conn


class TestSyncLogger:
    @pytest.mark.asyncio
    async def test_log_success(self) -> None:
        conn = _make_conn()
        conn.execute = AsyncMock()

        logger = SyncLogger(conn=conn)
        await logger.log_sync(
            direction="inbound",
            files_updated=5,
            files_checked=10,
            duration_ms=1200,
            status="success",
        )
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "INSERT INTO sync_log" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_log_failure(self) -> None:
        conn = _make_conn()
        conn.execute = AsyncMock()

        logger = SyncLogger(conn=conn)
        await logger.log_sync(
            direction="inbound",
            files_updated=0,
            files_checked=0,
            duration_ms=500,
            status="error",
            error="Connection refused",
        )
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_recent_sync(self) -> None:
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value={"synced_at": datetime.now(UTC)})

        logger = SyncLogger(conn=conn)
        healthy = await logger.check_health(max_age_minutes=20)
        assert healthy is True

    @pytest.mark.asyncio
    async def test_check_health_no_sync(self) -> None:
        conn = _make_conn()
        conn.fetchrow = AsyncMock(return_value=None)

        logger = SyncLogger(conn=conn)
        healthy = await logger.check_health(max_age_minutes=20)
        assert healthy is False
