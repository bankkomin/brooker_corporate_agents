"""Tests for email sender."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_send_email_calls_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_email should connect to SMTP and send the message."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.local")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "bot@brooker.test")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@brooker.test")

    mock_smtp = AsyncMock()
    mock_smtp.__aenter__ = AsyncMock(return_value=mock_smtp)
    mock_smtp.__aexit__ = AsyncMock(return_value=False)
    mock_smtp.sendmail = AsyncMock()

    with patch("services.email_notifier.src.email_sender.aiosmtplib.SMTP", return_value=mock_smtp):
        # Re-import to pick up env vars
        from services.email_notifier.src.email_sender import send_email

        await send_email(
            to="hod@brooker.test",
            subject="New Proposal",
            html_body="<h1>Hello</h1>",
        )

    mock_smtp.__aenter__.assert_awaited_once()
    mock_smtp.sendmail.assert_awaited_once()
    call_args = mock_smtp.sendmail.call_args
    assert call_args[0][0] == "noreply@brooker.test"  # sender
    assert call_args[0][1] == "hod@brooker.test"  # recipient


@pytest.mark.asyncio
async def test_send_email_no_smtp_logs_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When SMTP_HOST is not set, send_email should log a warning and not crash."""
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    # Force module reload to pick up cleared env
    import importlib

    import services.email_notifier.src.email_sender as mod

    importlib.reload(mod)

    with caplog.at_level(logging.WARNING):
        await mod.send_email(
            to="hod@brooker.test",
            subject="Test",
            html_body="<p>test</p>",
        )

    assert any("SMTP not configured" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_send_proposal_notification_renders_template(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keypair: tuple[bytes, bytes],
) -> None:
    """send_proposal_notification should render HTML and call send_email."""
    monkeypatch.setenv("SMTP_HOST", "smtp.test.local")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "bot@brooker.test")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@brooker.test")
    monkeypatch.setenv("DASHBOARD_URL", "https://approve.brooker.test")

    from services.email_notifier.src.models import ProposalNotification

    proposal = ProposalNotification(
        proposal_id="chg_0001",
        agent_name="liquidity-agent",
        file="ALCO_Tracker.xlsx",
        tab="Liquidity",
        cell="D10",
        new_value="1.18",
        confidence=0.91,
        dept="cac",
    )

    private_pem, _ = rsa_keypair

    with patch("services.email_notifier.src.email_sender.send_email", new_callable=AsyncMock) as m:
        from services.email_notifier.src.email_sender import send_proposal_notification

        await send_proposal_notification(
            proposal=proposal,
            token="fake-jwt-token",
            hod_email="hod@brooker.test",
        )

    m.assert_awaited_once()
    call_kwargs = m.call_args
    assert call_kwargs[1]["to"] == "hod@brooker.test"
    assert "chg_0001" in call_kwargs[1]["subject"]
    assert "fake-jwt-token" in call_kwargs[1]["html_body"]


@pytest.mark.asyncio
async def test_send_reminder_uses_token_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_reminder should produce a URL with ?token= and NOT ?proposal=."""
    monkeypatch.setenv("DASHBOARD_URL", "https://approve.brooker.test")

    target = "services.email_notifier.src.email_sender.send_email"
    with patch(target, new_callable=AsyncMock) as mock_send:
        from services.email_notifier.src.email_sender import send_reminder

        await send_reminder(
            proposal_id="chg_0042",
            recipient="hod@brooker.test",
            token="reminder-jwt-token",
        )

    mock_send.assert_awaited_once()
    html_body = mock_send.call_args[1]["html_body"]
    assert "?token=reminder-jwt-token" in html_body
    assert "?proposal=" not in html_body
