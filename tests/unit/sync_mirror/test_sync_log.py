"""Tests for Postgres sync_log insertion and health check."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.sync_mirror.src.sync_log import SyncLogger


def _make_conn(mock_cursor: AsyncMock) -> MagicMock:
    """Build a mock conn with .cursor() async-context-manager."""
    mock_conn = MagicMock()
    mock_conn.commit = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.cursor.return_value = ctx
    return mock_conn


class TestSyncLogger:
    @pytest.mark.asyncio
    async def test_log_success(self) -> None:
        mock_cursor = AsyncMock()
        mock_conn = _make_conn(mock_cursor)

        logger = SyncLogger(conn=mock_conn)
        await logger.log_sync(
            direction="inbound",
            source="smb",
            files_synced=5,
            status="success",
        )
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert "INSERT INTO sync_log" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_log_failure(self) -> None:
        mock_cursor = AsyncMock()
        mock_conn = _make_conn(mock_cursor)

        logger = SyncLogger(conn=mock_conn)
        await logger.log_sync(
            direction="inbound",
            source="smb",
            files_synced=0,
            status="error",
            error_detail="Connection refused",
        )
        mock_cursor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_recent_sync(self) -> None:
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(datetime.now(UTC),))
        mock_conn = _make_conn(mock_cursor)

        logger = SyncLogger(conn=mock_conn)
        healthy = await logger.check_health(max_age_minutes=20)
        assert healthy is True

    @pytest.mark.asyncio
    async def test_check_health_no_sync(self) -> None:
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)
        mock_conn = _make_conn(mock_cursor)

        logger = SyncLogger(conn=mock_conn)
        healthy = await logger.check_health(max_age_minutes=20)
        assert healthy is False
