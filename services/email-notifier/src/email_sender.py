"""Async SMTP email sender with Jinja2 HTML templates."""
from __future__ import annotations

import asyncio
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
import asyncpg
from jinja2 import Environment, FileSystemLoader

from .db_logger import log_email_attempt, update_email_status
from .models import EscalationNotification, ProposalNotification
from .slack_alert import alert_smtp_failure

logger = logging.getLogger("email-notifier.sender")

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def _smtp_configured() -> bool:
    """Check if SMTP environment variables are set."""
    return bool(os.environ.get("SMTP_HOST"))


async def send_email(to: str, subject: str, html_body: str) -> None:
    """Send an HTML email via SMTP.

    If SMTP is not configured (SMTP_HOST not set), logs a warning and returns
    without raising an error.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_body: HTML content of the email.
    """
    if not _smtp_configured():
        logger.warning("SMTP not configured — skipping email to %s: %s", to, subject)
        return

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    async with aiosmtplib.SMTP(
        hostname=smtp_host,
        port=smtp_port,
        use_tls=True,
    ) as smtp:
        if smtp_user and smtp_password:
            await smtp.login(smtp_user, smtp_password)
        await smtp.sendmail(smtp_from, to, msg.as_string())

    logger.info("Email sent to %s: %s", to, subject)


# Exponential back-off delays between attempts (seconds).
_RETRY_DELAYS = [1.0, 4.0, 16.0]


async def send_email_with_retry(
    *,
    to: str,
    subject: str,
    html_body: str,
    pool: asyncpg.Pool | None = None,
    event_type: str = "proposal",
    proposal_id: str | None = None,
    dept: str | None = None,
) -> None:
    """Send an email with retry logic, DB logging, and Slack alert on exhaustion.

    Wraps :func:`send_email` with up to ``len(_RETRY_DELAYS)`` attempts using
    exponential back-off (1 s → 4 s → 16 s).  Each attempt is recorded in the
    ``email_log`` table.  When all attempts fail a Slack alert is fired via
    :func:`alert_smtp_failure`.

    If *pool* is ``None`` the function degrades gracefully to a single
    :func:`send_email` call with no DB logging.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_body: Rendered HTML body.
        pool: asyncpg connection pool for DB logging; if ``None`` logging is skipped.
        event_type: Category recorded in ``email_log.event_type``.
        proposal_id: Optional proposal identifier for the log row.
        dept: Optional department code for the log row.
    """
    if pool is None:
        await send_email(to=to, subject=subject, html_body=html_body)
        return

    log_id = await log_email_attempt(
        pool,
        recipient=to,
        event_type=event_type,
        proposal_id=proposal_id,
        dept=dept,
        subject=subject,
        status="pending",
    )

    last_error: str | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            await send_email(to=to, subject=subject, html_body=html_body)
            await update_email_status(pool, log_id, status="sent")
            logger.info("email.sent to=%s attempt=%d", to, attempt + 1)
            return
        except Exception as exc:
            last_error = str(exc)
            next_delay = delay if attempt < len(_RETRY_DELAYS) - 1 else None
            logger.warning(
                "email.retry to=%s attempt=%d/%d error=%s next_delay=%s",
                to,
                attempt + 1,
                len(_RETRY_DELAYS),
                last_error,
                next_delay,
            )
            # Use 'pending' — 'retrying' is not a valid delivery_status value.
            # email_log CHECK constraint allows only: sent, delivered, failed, bounced, pending.
            await update_email_status(
                pool,
                log_id,
                status="pending",
                error=last_error,
                retry_count=attempt + 1,
            )
            if attempt < len(_RETRY_DELAYS) - 1:
                await asyncio.sleep(delay)

    # All retries exhausted.
    await update_email_status(
        pool,
        log_id,
        status="failed",
        error=last_error,
        retry_count=len(_RETRY_DELAYS),
    )
    await alert_smtp_failure(
        recipient=to,
        subject=subject,
        error_detail=last_error or "Unknown error",
    )
    logger.error("email.all_retries_exhausted to=%s error=%s", to, last_error)


async def send_proposal_notification(
    proposal: ProposalNotification,
    token: str,
    hod_email: str,
    pool: asyncpg.Pool | None = None,
) -> None:
    """Render the proposal template and send it to the HOD.

    Args:
        proposal: The proposal notification payload.
        token: JWT token for the approval deep-link.
        hod_email: HOD email address to send to.
        pool: Optional asyncpg pool for DB logging and retry; skipped if ``None``.
    """
    dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:4000")
    template = _jinja_env.get_template("proposal.html")
    html_body = template.render(
        proposal_id=proposal.proposal_id,
        agent_name=proposal.agent_name,
        file=proposal.file,
        tab=proposal.tab,
        cell=proposal.cell,
        new_value=proposal.new_value,
        confidence=proposal.confidence,
        approve_url=f"{dashboard_url}/approve?token={token}",
        token=token,
    )
    await send_email_with_retry(
        to=hod_email,
        subject=f"[Action Required] Proposal {proposal.proposal_id} needs your review",
        html_body=html_body,
        pool=pool,
        event_type="proposal",
        proposal_id=proposal.proposal_id,
        dept=proposal.dept,
    )


async def send_reminder(
    proposal_id: str,
    recipient: str,
    token: str,
    pool: asyncpg.Pool | None = None,
) -> None:
    """Send a reminder email for a pending proposal.

    Args:
        proposal_id: Identifier of the proposal requiring action.
        recipient: HOD email address.
        token: JWT token for the approval deep-link.
        pool: Optional asyncpg pool for DB logging and retry; skipped if ``None``.
    """
    dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:4000")
    template = _jinja_env.get_template("reminder.html")
    html_body = template.render(
        proposal_id=proposal_id,
        approve_url=f"{dashboard_url}/approve?token={token}",
    )
    await send_email_with_retry(
        to=recipient,
        subject=f"[Reminder] Proposal {proposal_id} awaiting your review",
        html_body=html_body,
        pool=pool,
        event_type="reminder",
        proposal_id=proposal_id,
    )


async def send_confirmed(
    proposal_id: str,
    decision: str,
    recipient: str,
    pool: asyncpg.Pool | None = None,
) -> None:
    """Send a confirmation email after a proposal decision.

    Args:
        proposal_id: Identifier of the decided proposal.
        decision: Human-readable outcome (e.g. "approved", "rejected").
        recipient: Email address to notify.
        pool: Optional asyncpg pool for DB logging and retry; skipped if ``None``.
    """
    template = _jinja_env.get_template("confirmed.html")
    html_body = template.render(proposal_id=proposal_id, decision=decision)
    await send_email_with_retry(
        to=recipient,
        subject=f"Proposal {proposal_id} has been {decision}",
        html_body=html_body,
        pool=pool,
        event_type="confirmed",
        proposal_id=proposal_id,
    )


async def send_rejection(
    proposal_id: str,
    reason: str,
    recipient: str,
    pool: asyncpg.Pool | None = None,
) -> None:
    """Send a rejection notification email.

    Args:
        proposal_id: Identifier of the rejected proposal.
        reason: Human-readable reason for rejection.
        recipient: Email address to notify.
        pool: Optional asyncpg pool for DB logging and retry; skipped if ``None``.
    """
    template = _jinja_env.get_template("rejection.html")
    html_body = template.render(proposal_id=proposal_id, reason=reason)
    await send_email_with_retry(
        to=recipient,
        subject=f"Proposal {proposal_id} was rejected",
        html_body=html_body,
        pool=pool,
        event_type="rejected",
        proposal_id=proposal_id,
    )


async def send_escalation(
    payload: EscalationNotification,
    recipients: list[str],
    pool: asyncpg.Pool | None = None,
) -> None:
    """Render escalation.html and send to all recipients (HOD + CEO).

    Args:
        payload: The escalation notification payload.
        recipients: List of email addresses to notify (HOD and/or CEO).
        pool: Optional asyncpg pool for DB logging and retry; skipped if ``None``.
    """
    template = _jinja_env.get_template("escalation.html")
    dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:4000")
    html_body = template.render(
        severity=payload.severity,
        agent_name=payload.agent_name,
        escalation_detail=payload.escalation_detail,
        query=payload.query,
        channel=payload.channel,
        dashboard_url=dashboard_url,
    )
    subject = f"[{payload.severity.upper()}] Escalation — {payload.agent_name}"
    for recipient in recipients:
        await send_email_with_retry(
            to=recipient,
            subject=subject,
            html_body=html_body,
            pool=pool,
            event_type="escalation",
            proposal_id=None,
            dept=payload.dept,
        )
