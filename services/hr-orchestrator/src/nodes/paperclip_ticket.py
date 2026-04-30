"""Paperclip ticket creation node for HR -- always type "query" (no proposals)."""
from __future__ import annotations

import asyncio

import httpx
import structlog

logger = structlog.get_logger("hr-orchestrator.paperclip")

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0


async def _post_ticket(
    url: str,
    api_key: str,
    payload: dict,
) -> str | None:
    """POST to Paperclip /tickets with exponential backoff retry."""
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    for attempt in range(_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                ticket_id: str = data["ticket_id"]
                logger.info(
                    "paperclip_ticket_created",
                    ticket_id=ticket_id,
                    agent=payload.get("agent"),
                    department=payload.get("department"),
                )
                return ticket_id
        except Exception as exc:
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(
                "paperclip_ticket_retry",
                attempt=attempt + 1,
                error=str(exc),
                delay=delay,
            )
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay)

    logger.error("paperclip_ticket_failed", max_retries=_MAX_RETRIES)
    return None


async def create_paperclip_ticket(
    state: dict,
    *,
    paperclip_url: str,
    paperclip_api_key: str,
) -> dict:
    """Create a Paperclip ticket for the completed HR query.

    HR is read-only: ticket type is always "query" (never "proposal").
    """
    api_payload = {
        "type": "query",
        "department": "hr",
        "agent": state.get("agent_name", "unknown"),
        "interaction_id": str(state["interaction_id"]) if state.get("interaction_id") else None,
        "payload": {
            "query": state.get("query", "")[:200],
            "intent": state.get("intent", ""),
            "confidence_score": state.get("confidence_score", 0.0),
            "escalation_triggered": state.get("escalation_triggered", False),
        },
    }

    ticket_id = await _post_ticket(
        url=f"{paperclip_url}/tickets",
        api_key=paperclip_api_key,
        payload=api_payload,
    )

    if ticket_id is None:
        ticket_id = f"PPC-LOCAL-{state.get('interaction_id', '?')}"
        logger.warning(
            "paperclip_ticket_fallback",
            ticket_id=ticket_id,
            reason="service_unreachable",
        )

    return {"paperclip_ticket_id": ticket_id}
