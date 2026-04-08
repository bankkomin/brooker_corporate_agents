"""Tests for the APScheduler check_overdue_proposals job."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_pool(overdue_rows: list, already_reminded_rows: list) -> MagicMock:
    """Return a minimal asyncpg Pool mock whose conn.fetch returns the given sequences.

    The scheduler calls conn.fetch exactly twice inside a single acquire():
      1. SELECT staging_proposals → overdue_rows
      2. SELECT email_log         → already_reminded_rows

    If overdue_rows is empty the second fetch is never reached (early return).
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[overdue_rows, already_reminded_rows])

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool


def _proposal_row(proposal_id: str, dept: str) -> dict:
    return {"proposal_id": proposal_id, "dept": dept}


def _email_log_row(proposal_id: str) -> dict:
    return {"proposal_id": proposal_id}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_overdue_proposals_sends_reminder() -> None:
    """An overdue proposal with no existing reminder today triggers send_reminder."""
    overdue = [_proposal_row("chg_0001", "cac")]
    already_reminded: list = []

    pool = _make_mock_pool(overdue, already_reminded)

    with (
        patch(
            "services.email_notifier.src.scheduler.send_reminder",
            new_callable=AsyncMock,
        ) as mock_send,
        patch(
            "services.email_notifier.src.scheduler.generate_proposal_token",
            return_value="mock-jwt",
        ) as mock_token,
    ):
        from services.email_notifier.src.scheduler import check_overdue_proposals

        sent = await check_overdue_proposals(
            pool=pool,
            resolve_hod_email=lambda dept: "hod@brooker.test",
        )

    assert sent == 1
    mock_token.assert_called_once_with(
        proposal_id="chg_0001",
        dept="cac",
        hod_email="hod@brooker.test",
    )
    mock_send.assert_awaited_once_with(
        proposal_id="chg_0001",
        recipient="hod@brooker.test",
        token="mock-jwt",
        pool=pool,
    )


@pytest.mark.asyncio
async def test_check_overdue_proposals_skips_already_reminded() -> None:
    """A proposal that already received a reminder today must be skipped."""
    overdue = [_proposal_row("chg_0002", "cac")]
    already_reminded = [_email_log_row("chg_0002")]

    pool = _make_mock_pool(overdue, already_reminded)

    with patch(
        "services.email_notifier.src.scheduler.send_reminder",
        new_callable=AsyncMock,
    ) as mock_send:
        from services.email_notifier.src.scheduler import check_overdue_proposals

        sent = await check_overdue_proposals(
            pool=pool,
            resolve_hod_email=lambda dept: "hod@brooker.test",
        )

    assert sent == 0
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_overdue_proposals_no_overdue() -> None:
    """When no proposals are pending > 24h the function returns 0 immediately."""
    # Second fetch (email_log) is never called because of the early return.
    pool = _make_mock_pool(overdue_rows=[], already_reminded_rows=[])

    with patch(
        "services.email_notifier.src.scheduler.send_reminder",
        new_callable=AsyncMock,
    ) as mock_send:
        from services.email_notifier.src.scheduler import check_overdue_proposals

        sent = await check_overdue_proposals(
            pool=pool,
            resolve_hod_email=lambda dept: "hod@brooker.test",
        )

    assert sent == 0
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_overdue_proposals_skips_missing_hod_email() -> None:
    """Proposals where no HOD email can be resolved must be skipped, not crash."""
    overdue = [_proposal_row("chg_0003", "unknown_dept")]
    already_reminded: list = []

    pool = _make_mock_pool(overdue, already_reminded)

    with patch(
        "services.email_notifier.src.scheduler.send_reminder",
        new_callable=AsyncMock,
    ) as mock_send:
        from services.email_notifier.src.scheduler import check_overdue_proposals

        sent = await check_overdue_proposals(
            pool=pool,
            resolve_hod_email=lambda dept: None,  # no email for any dept
        )

    assert sent == 0
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_overdue_proposals_mixed_batch() -> None:
    """Only proposals that are overdue AND not yet reminded AND have a HOD email get a reminder."""
    overdue = [
        _proposal_row("chg_0010", "cac"),   # should be reminded
        _proposal_row("chg_0011", "cac"),   # already reminded today → skip
        _proposal_row("chg_0012", "ghost"), # no HOD email → skip
    ]
    already_reminded = [_email_log_row("chg_0011")]

    pool = _make_mock_pool(overdue, already_reminded)

    def fake_resolve(dept: str) -> str | None:
        return "hod@brooker.test" if dept == "cac" else None

    with (
        patch(
            "services.email_notifier.src.scheduler.send_reminder",
            new_callable=AsyncMock,
        ) as mock_send,
        patch(
            "services.email_notifier.src.scheduler.generate_proposal_token",
            return_value="mock-jwt",
        ),
    ):
        from services.email_notifier.src.scheduler import check_overdue_proposals

        sent = await check_overdue_proposals(pool=pool, resolve_hod_email=fake_resolve)

    assert sent == 1
    # Only chg_0010 should have triggered a send
    call_kwargs = mock_send.await_args_list[0].kwargs
    assert call_kwargs["proposal_id"] == "chg_0010"
