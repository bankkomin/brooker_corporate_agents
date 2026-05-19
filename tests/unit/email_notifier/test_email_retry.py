"""Tests for send_email_with_retry — retry logic, DB logging, and Slack alerting."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_pool() -> MagicMock:
    """Return a minimal asyncpg Pool mock that supports pool.acquire() as ctx manager."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 42})
    conn.execute = AsyncMock()

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_email_with_retry_succeeds_first_attempt() -> None:
    """When send_email succeeds on the first try the log row status should be 'sent'."""
    pool = _make_mock_pool()

    with (
        patch(
            "services.email_notifier.src.email_sender.send_email",
            new_callable=AsyncMock,
        ) as mock_send,
        patch(
            "services.email_notifier.src.email_sender.log_email_attempt",
            new_callable=AsyncMock,
            return_value=42,
        ) as mock_log,
        patch(
            "services.email_notifier.src.email_sender.update_email_status",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        from services.email_notifier.src.email_sender import send_email_with_retry

        await send_email_with_retry(
            to="hod@brooker.test",
            subject="Test subject",
            html_body="<p>body</p>",
            pool=pool,
            event_type="proposal",
            proposal_id="chg_0001",
            dept="cac",
        )

    mock_send.assert_awaited_once()
    mock_log.assert_awaited_once_with(
        pool,
        recipient="hod@brooker.test",
        event_type="proposal",
        proposal_id="chg_0001",
        dept="cac",
        subject="Test subject",
        status="pending",
    )
    mock_update.assert_awaited_once_with(pool, 42, status="sent")


@pytest.mark.asyncio
async def test_send_email_with_retry_succeeds_on_second_attempt() -> None:
    """First send_email raises; second succeeds — retry_count=1 logged, final status 'sent'."""
    pool = _make_mock_pool()

    smtp_error = OSError("SMTP connection refused")
    send_side_effects = [smtp_error, None]

    with (
        patch(
            "services.email_notifier.src.email_sender.send_email",
            new_callable=AsyncMock,
            side_effect=send_side_effects,
        ) as mock_send,
        patch(
            "services.email_notifier.src.email_sender.log_email_attempt",
            new_callable=AsyncMock,
            return_value=7,
        ),
        patch(
            "services.email_notifier.src.email_sender.update_email_status",
            new_callable=AsyncMock,
        ) as mock_update,
        patch("services.email_notifier.src.email_sender.asyncio.sleep", new_callable=AsyncMock),
    ):
        from services.email_notifier.src.email_sender import send_email_with_retry

        await send_email_with_retry(
            to="hod@brooker.test",
            subject="Retry test",
            html_body="<p>body</p>",
            pool=pool,
            event_type="reminder",
        )

    assert mock_send.await_count == 2

    # First update: retrying with retry_count=1
    retrying_call = call(
        pool,
        7,
        status="retrying",
        error=str(smtp_error),
        retry_count=1,
    )
    # Second update: sent
    sent_call = call(pool, 7, status="sent")
    mock_update.assert_has_awaits([retrying_call, sent_call])


@pytest.mark.asyncio
async def test_send_email_with_retry_exhausted_logs_failure() -> None:
    """All 3 attempts fail — email_log row should end with status='failed' and retry_count=3."""
    pool = _make_mock_pool()
    smtp_error = OSError("connection timed out")

    with (
        patch(
            "services.email_notifier.src.email_sender.send_email",
            new_callable=AsyncMock,
            side_effect=smtp_error,
        ) as mock_send,
        patch(
            "services.email_notifier.src.email_sender.log_email_attempt",
            new_callable=AsyncMock,
            return_value=99,
        ),
        patch(
            "services.email_notifier.src.email_sender.update_email_status",
            new_callable=AsyncMock,
        ) as mock_update,
        patch("services.email_notifier.src.email_sender.asyncio.sleep", new_callable=AsyncMock),
        patch(
            "services.email_notifier.src.email_sender.alert_smtp_failure",
            new_callable=AsyncMock,
        ),
    ):
        from services.email_notifier.src.email_sender import send_email_with_retry

        await send_email_with_retry(
            to="hod@brooker.test",
            subject="Exhaustion test",
            html_body="<p>body</p>",
            pool=pool,
        )

    # All three retries attempted
    assert mock_send.await_count == 3

    # Final status update must be 'failed' with retry_count=3
    last_update = mock_update.await_args_list[-1]
    assert last_update == call(
        pool,
        99,
        status="failed",
        error=str(smtp_error),
        retry_count=3,
    )


@pytest.mark.asyncio
async def test_send_email_with_retry_alerts_slack_on_exhaustion() -> None:
    """After all retries fail, alert_smtp_failure must be called once with correct args."""
    pool = _make_mock_pool()
    smtp_error = OSError("AUTH failed")

    with (
        patch(
            "services.email_notifier.src.email_sender.send_email",
            new_callable=AsyncMock,
            side_effect=smtp_error,
        ),
        patch(
            "services.email_notifier.src.email_sender.log_email_attempt",
            new_callable=AsyncMock,
            return_value=5,
        ),
        patch(
            "services.email_notifier.src.email_sender.update_email_status",
            new_callable=AsyncMock,
        ),
        patch("services.email_notifier.src.email_sender.asyncio.sleep", new_callable=AsyncMock),
        patch(
            "services.email_notifier.src.email_sender.alert_smtp_failure",
            new_callable=AsyncMock,
        ) as mock_alert,
    ):
        from services.email_notifier.src.email_sender import send_email_with_retry

        await send_email_with_retry(
            to="hod@brooker.test",
            subject="Alert test",
            html_body="<p>body</p>",
            pool=pool,
        )

    mock_alert.assert_awaited_once_with(
        recipient="hod@brooker.test",
        subject="Alert test",
        error_detail=str(smtp_error),
    )


@pytest.mark.asyncio
async def test_send_email_with_retry_no_pool_falls_back_to_send_email() -> None:
    """When pool=None the function calls send_email directly with no DB interaction."""
    with (
        patch(
            "services.email_notifier.src.email_sender.send_email",
            new_callable=AsyncMock,
        ) as mock_send,
        patch(
            "services.email_notifier.src.email_sender.log_email_attempt",
            new_callable=AsyncMock,
        ) as mock_log,
    ):
        from services.email_notifier.src.email_sender import send_email_with_retry

        await send_email_with_retry(
            to="hod@brooker.test",
            subject="No pool test",
            html_body="<p>body</p>",
            pool=None,
        )

    mock_send.assert_awaited_once_with(
        to="hod@brooker.test",
        subject="No pool test",
        html_body="<p>body</p>",
    )
    mock_log.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_email_with_retry_backoff_delays_between_attempts() -> None:
    """asyncio.sleep must be called with the correct back-off delays (1.0, 4.0)."""
    pool = _make_mock_pool()
    smtp_error = OSError("timeout")

    with (
        patch(
            "services.email_notifier.src.email_sender.send_email",
            new_callable=AsyncMock,
            side_effect=smtp_error,
        ),
        patch(
            "services.email_notifier.src.email_sender.log_email_attempt",
            new_callable=AsyncMock,
            return_value=1,
        ),
        patch(
            "services.email_notifier.src.email_sender.update_email_status",
            new_callable=AsyncMock,
        ),
        patch(
            "services.email_notifier.src.email_sender.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        patch(
            "services.email_notifier.src.email_sender.alert_smtp_failure",
            new_callable=AsyncMock,
        ),
    ):
        from services.email_notifier.src.email_sender import send_email_with_retry

        await send_email_with_retry(
            to="hod@brooker.test",
            subject="Backoff test",
            html_body="<p>body</p>",
            pool=pool,
        )

    # Delays 1.0 and 4.0 are used between attempts 1-2 and 2-3; no sleep after last attempt.
    assert mock_sleep.await_count == 2
    mock_sleep.assert_has_awaits([call(1.0), call(4.0)])
