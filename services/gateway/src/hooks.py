"""Post-decision hooks — fire-and-forget triggers to downstream services."""
from __future__ import annotations

import os

import httpx
import structlog

logger = structlog.get_logger("gateway.hooks")

SYNC_BACK_URL = os.environ.get("SYNC_BACK_URL", "http://sync-back:3006")
EMAIL_NOTIFIER_URL = os.environ.get("EMAIL_NOTIFIER_URL", "http://email-notifier:3005")


async def on_proposal_approved(proposal_id: str, dept: str) -> None:
    """Trigger sync-back and confirmation email after approval.

    Fire-and-forget: logs errors but never raises, so the gateway response
    to the user is not blocked by downstream failures.

    Args:
        proposal_id: The approved proposal ID.
        dept: Department for email routing.
    """
    # 1. Trigger sync-back to process the approved proposal
    await _post_fire_and_forget(
        f"{SYNC_BACK_URL}/process-approved",
        {},  # No body needed - sync-back queries DB for all approved
        "sync-back",
        proposal_id,
    )

    # 2. Trigger confirmation email
    await _post_fire_and_forget(
        f"{EMAIL_NOTIFIER_URL}/notify/confirmed",
        {"proposal_id": proposal_id, "decision": "approved", "dept": dept},
        "email-notifier",
        proposal_id,
    )


async def on_proposal_rejected(proposal_id: str, dept: str, reason: str | None = None) -> None:
    """Trigger rejection notification email after rejection.

    No sync-back needed for rejections.

    Args:
        proposal_id: The rejected proposal ID.
        dept: Department for email routing.
        reason: Rejection reason (optional).
    """
    await _post_fire_and_forget(
        f"{EMAIL_NOTIFIER_URL}/notify/confirmed",
        {"proposal_id": proposal_id, "decision": "rejected", "dept": dept},
        "email-notifier",
        proposal_id,
    )


async def _post_fire_and_forget(
    url: str,
    json_body: dict,
    service_name: str,
    proposal_id: str,
) -> None:
    """POST to a service endpoint. Log errors but never raise."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=json_body)
            resp.raise_for_status()
        logger.info(
            f"hook.{service_name}.success",
            proposal_id=proposal_id,
            url=url,
            status_code=resp.status_code,
        )
    except Exception as exc:
        logger.error(
            f"hook.{service_name}.failed",
            proposal_id=proposal_id,
            url=url,
            error=str(exc),
        )
