"""Unit tests for sync-back rollback module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.sync_back.src.rollback import handle_failure

# ---------------------------------------------------------------------------
# Helpers — mirrors the _FakeAcquire pattern from test_approval_flow.py
# ---------------------------------------------------------------------------


class _FakeAcquire:
    """Async context manager mimicking asyncpg pool.acquire()."""

    def __init__(self, conn: AsyncMock) -> None:
        self._conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self._conn

    async def __aexit__(self, *args: object) -> None:
        pass


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Create a mock asyncpg pool with connection context manager."""
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = _FakeAcquire(conn)
    return pool, conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRollbackCleansStagingDir:
    """handle_failure removes staging/approved/{proposal_id}/ on failure."""

    @pytest.mark.asyncio
    async def test_rollback_cleans_staging_dir(self, tmp_path: Path) -> None:
        """Staging directory and its contents are deleted by handle_failure."""
        proposal_id = "chg_0001"

        # Create staging/approved/{proposal_id}/ with a dummy file
        staging_dir = tmp_path / "approved" / proposal_id
        staging_dir.mkdir(parents=True)
        (staging_dir / "manifest.json").write_text('{"id": "chg_0001"}', encoding="utf-8")
        (staging_dir / "ALCO_Tracker.xlsx").write_bytes(b"fake-excel-content")

        assert staging_dir.exists()

        pool, conn = _mock_pool()

        with patch(
            "services.sync_back.src.rollback.STAGING_PATH",
            str(tmp_path),
        ):
            await handle_failure(proposal_id, pool, "write error")

        # Directory must be gone
        assert not staging_dir.exists()


class TestRollbackRevertsDbStatus:
    """handle_failure reverts DB status to 'pending'."""

    @pytest.mark.asyncio
    async def test_rollback_reverts_db_status(self, tmp_path: Path) -> None:
        """UPDATE SQL is executed with status='pending' and the correct proposal_id."""
        proposal_id = "chg_0042"
        pool, conn = _mock_pool()

        with patch(
            "services.sync_back.src.rollback.STAGING_PATH",
            str(tmp_path),
        ):
            await handle_failure(proposal_id, pool, "openpyxl failure")

        # Verify execute was called
        conn.execute.assert_called_once()
        sql, *args = conn.execute.call_args[0]

        assert "staging_proposals" in sql
        assert "status = 'pending'" in sql
        assert "synced_at = NULL" in sql
        # proposal_id passed as positional parameter
        assert proposal_id in args


class TestRollbackAlertsSlack:
    """handle_failure POSTs failure alert to the Slack webhook when configured."""

    @pytest.mark.asyncio
    async def test_rollback_alerts_slack(self, tmp_path: Path) -> None:
        """httpx POST is made to SLACK_WEBHOOK_URL with failure details."""
        proposal_id = "chg_0099"
        webhook_url = "https://hooks.slack.com/services/FAKE/WEBHOOK"
        pool, _conn = _mock_pool()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("services.sync_back.src.rollback.STAGING_PATH", str(tmp_path)),
            patch("services.sync_back.src.rollback.SLACK_WEBHOOK_URL", webhook_url),
            patch("services.sync_back.src.rollback.httpx.AsyncClient", return_value=mock_client),
        ):
            await handle_failure(proposal_id, pool, "disk full")

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args

        # First positional arg is the URL
        posted_url = call_kwargs[0][0]
        assert posted_url == webhook_url

        # Payload contains proposal_id and error info
        payload = call_kwargs[1]["json"]
        assert proposal_id in payload["text"]
        assert "disk full" in payload["text"]


class TestRollbackNoSlackWebhook:
    """handle_failure skips Slack silently when SLACK_WEBHOOK_URL is empty."""

    @pytest.mark.asyncio
    async def test_rollback_no_slack_webhook_skips_silently(self, tmp_path: Path) -> None:
        """No HTTP call made when SLACK_WEBHOOK_URL is unset/empty."""
        pool, _conn = _mock_pool()

        with (
            patch("services.sync_back.src.rollback.STAGING_PATH", str(tmp_path)),
            patch("services.sync_back.src.rollback.SLACK_WEBHOOK_URL", ""),
            patch("services.sync_back.src.rollback.httpx.AsyncClient") as mock_cls,
        ):
            await handle_failure("chg_0000", pool, "some error")

        # AsyncClient must not have been instantiated
        mock_cls.assert_not_called()


class TestRollbackMissingStagingDir:
    """handle_failure is safe when staging directory does not exist."""

    @pytest.mark.asyncio
    async def test_rollback_missing_staging_dir_is_safe(self, tmp_path: Path) -> None:
        """No exception raised when staging/approved/{id}/ was never created."""
        proposal_id = "chg_9999"
        pool, conn = _mock_pool()

        # Directory deliberately absent
        staging_dir = tmp_path / "approved" / proposal_id
        assert not staging_dir.exists()

        with patch("services.sync_back.src.rollback.STAGING_PATH", str(tmp_path)):
            # Must not raise
            await handle_failure(proposal_id, pool, "never wrote")

        # DB revert still executed
        conn.execute.assert_called_once()
