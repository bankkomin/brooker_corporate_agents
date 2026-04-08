"""Tests for email_log DB logging functions."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class _FakeAcquire:
    """Async context manager mimicking asyncpg pool.acquire()."""

    def __init__(self, conn: AsyncMock) -> None:
        self._conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = _FakeAcquire(conn)
    return pool, conn


class TestLogEmailAttempt:
    """Tests for log_email_attempt()."""

    @pytest.mark.asyncio
    async def test_inserts_row_and_returns_id(self) -> None:
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"id": 42})

        from services.email_notifier.src.db_logger import log_email_attempt

        log_id = await log_email_attempt(
            pool,
            recipient="hod@test.com",
            event_type="proposal",
            proposal_id="chg_0001",
            dept="cac",
            subject="Test subject",
        )

        assert log_id == 42
        conn.fetchrow.assert_awaited_once()
        sql = conn.fetchrow.call_args[0][0]
        assert "INSERT INTO email_log" in sql
        assert "RETURNING id" in sql

    @pytest.mark.asyncio
    async def test_passes_all_parameters(self) -> None:
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"id": 1})

        from services.email_notifier.src.db_logger import log_email_attempt

        await log_email_attempt(
            pool,
            recipient="r@test.com",
            event_type="escalation",
            proposal_id="chg_0099",
            dept="risk",
            subject="Escalation",
            status="pending",
            error=None,
            retry_count=0,
        )

        args = conn.fetchrow.call_args[0]
        # Positional args after the SQL string
        assert args[1] == "r@test.com"       # recipient
        assert args[2] == "escalation"       # event_type
        assert args[3] == "chg_0099"         # proposal_id
        assert args[4] == "risk"             # dept
        assert args[5] == "Escalation"       # subject
        assert args[6] == "pending"          # status

    @pytest.mark.asyncio
    async def test_default_status_is_pending(self) -> None:
        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(return_value={"id": 1})

        from services.email_notifier.src.db_logger import log_email_attempt

        await log_email_attempt(
            pool,
            recipient="r@test.com",
            event_type="proposal",
            subject="Test",
        )

        args = conn.fetchrow.call_args[0]
        assert args[6] == "pending"  # status default


class TestUpdateEmailStatus:
    """Tests for update_email_status()."""

    @pytest.mark.asyncio
    async def test_updates_status_without_retry_count(self) -> None:
        pool, conn = _mock_pool()
        conn.execute = AsyncMock()

        from services.email_notifier.src.db_logger import update_email_status

        await update_email_status(pool, 42, status="sent")

        conn.execute.assert_awaited_once()
        sql = conn.execute.call_args[0][0]
        assert "delivery_status" in sql
        assert "retry_count" not in sql
        args = conn.execute.call_args[0]
        assert args[1] == "sent"
        assert args[3] == 42  # log_id

    @pytest.mark.asyncio
    async def test_updates_status_with_retry_count(self) -> None:
        pool, conn = _mock_pool()
        conn.execute = AsyncMock()

        from services.email_notifier.src.db_logger import update_email_status

        await update_email_status(
            pool, 42, status="retrying", error="SMTP timeout", retry_count=2,
        )

        conn.execute.assert_awaited_once()
        sql = conn.execute.call_args[0][0]
        assert "retry_count" in sql
        args = conn.execute.call_args[0]
        assert args[1] == "retrying"
        assert args[2] == "SMTP timeout"
        assert args[3] == 2   # retry_count
        assert args[4] == 42  # log_id

    @pytest.mark.asyncio
    async def test_updates_failed_with_error(self) -> None:
        pool, conn = _mock_pool()
        conn.execute = AsyncMock()

        from services.email_notifier.src.db_logger import update_email_status

        await update_email_status(
            pool, 7, status="failed", error="Connection refused", retry_count=3,
        )

        args = conn.execute.call_args[0]
        assert args[1] == "failed"
        assert args[2] == "Connection refused"
        assert args[3] == 3
