"""Escalation email notification node — fire-and-forget POST to email-notifier."""
from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger("cac-orchestrator.notify")


async def notify_escalation(state: dict, *, email_notifier_url: str) -> dict:
    """POST escalation to email-notifier if triggered. Fire-and-forget."""
    if not state.get("escalation_triggered"):
        return {}

    payload = {
        "escalation_detail": state.get("escalation_detail", ""),
        "agent_name": state.get("agent_name", ""),
        "query": state.get("query", ""),
        "user_id": state.get("user_id", ""),
        "channel": state.get("channel", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{email_notifier_url}/notify/escalation", json=payload
            )
            logger.info(
                "escalation_notified",
                status=resp.status_code,
                agent=payload["agent_name"],
            )
    except Exception as exc:
        logger.warning("escalation_notify_failed", error=str(exc))

    return {}
