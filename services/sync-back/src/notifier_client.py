"""Fire-and-forget client for email-notifier /notify/confirmed."""
from __future__ import annotations

import httpx
import structlog

from .config import EMAIL_NOTIFIER_URL

logger = structlog.get_logger("sync-back.notifier_client")


async def notify_confirmed(
    proposal_id: str,
    decision: str,
    dept: str,
) -> None:
    """POST to email-notifier /notify/confirmed after successful sync.

    Fire-and-forget with 10s timeout. Logs errors but never raises.

    Args:
        proposal_id: The synced proposal ID.
        decision: "approved" or "edited".
        dept: Department for HOD email resolution.
    """
    url = f"{EMAIL_NOTIFIER_URL}/notify/confirmed"
    payload = {
        "proposal_id": proposal_id,
        "decision": decision,
        "dept": dept,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
        logger.info(
            "notifier_client.confirmed_sent",
            proposal_id=proposal_id,
            status_code=resp.status_code,
        )
    except Exception as exc:
        logger.error(
            "notifier_client.confirmed_failed",
            proposal_id=proposal_id,
            error=str(exc),
        )
