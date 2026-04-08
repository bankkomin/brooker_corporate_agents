"""Fire-and-forget Slack webhook alerts for SMTP failures."""
from __future__ import annotations

import os

import httpx
import structlog

logger = structlog.get_logger("email-notifier.slack_alert")

SLACK_WEBHOOK_URL = os.environ.get("SLACK_ESCALATIONS_WEBHOOK_URL", "")


async def alert_smtp_failure(
    recipient: str,
    subject: str,
    error_detail: str,
) -> None:
    """POST to Slack #escalations webhook after all SMTP retries exhausted.

    Fire-and-forget with a 5 s timeout. Gracefully skips if the webhook URL
    is not configured via SLACK_ESCALATIONS_WEBHOOK_URL.

    Args:
        recipient: Email address that could not be reached.
        subject: Subject line of the failed email.
        error_detail: Last exception message from the SMTP layer.
    """
    webhook_url = os.environ.get("SLACK_ESCALATIONS_WEBHOOK_URL", SLACK_WEBHOOK_URL)
    if not webhook_url:
        logger.warning("slack_alert.no_webhook_configured", recipient=recipient)
        return

    payload = {
        "text": (
            ":rotating_light: *SMTP Failure \u2014 All retries exhausted*\n"
            f"*Recipient:* {recipient}\n"
            f"*Subject:* {subject}\n"
            f"*Error:* {error_detail}\n"
            "_Email-notifier could not deliver after 3 attempts._"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        logger.info("slack_alert.sent", recipient=recipient)
    except Exception as exc:
        logger.error("slack_alert.failed", error=str(exc), recipient=recipient)
