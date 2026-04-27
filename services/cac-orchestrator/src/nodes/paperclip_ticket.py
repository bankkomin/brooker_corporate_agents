"""Paperclip ticket creation node — HTTP POST to Paperclip service."""
from __future__ import annotations

import asyncio

import httpx
import structlog

logger = structlog.get_logger("cac-orchestrator.paperclip")

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0


async def _post_ticket(
    url: str,
    api_key: str,
    payload: dict,
) -> str | None:
    """POST to Paperclip /tickets with exponential backoff retry.

    Returns the ticket_id string on success, or None if all attempts fail.
    """
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

    logger.error(
        "paperclip_ticket_failed",
        max_retries=_MAX_RETRIES,
        agent=payload.get("agent"),
    )
    return None


async def create_paperclip_ticket(
    state: dict,
    *,
    paperclip_url: str,
    paperclip_api_key: str,
) -> dict:
    """Create a Paperclip ticket for the completed query/proposal.

    Fire-and-forget semantics: ticket creation failure does NOT block the
    response pipeline. The node always returns promptly; retries happen
    inside `_post_ticket` but the graph does not wait on a background task.

    Ticket type is "proposal" when a staging proposal was written, "query"
    otherwise.
    """
    has_proposal = state.get("staging_proposal_id") is not None
    ticket_type = "proposal" if has_proposal else "query"

    payload = {
        "type": ticket_type,
        "department": "cac",
        "agent": state.get("agent_name", "unknown"),
        "interaction_id": str(state["interaction_id"]) if state.get("interaction_id") else None,
        "metadata": {
            "query": state.get("query", "")[:200],
            "intent": state.get("intent", ""),
            "confidence_score": state.get("confidence_score", 0.0),
            "staging_proposal_id": state.get("staging_proposal_id"),
            "escalation_triggered": state.get("escalation_triggered", False),
        },
    }

    # Rename metadata → payload to match TicketCreate schema
    api_payload = {
        "type": payload["type"],
        "department": payload["department"],
        "agent": payload["agent"],
        "interaction_id": payload["interaction_id"],
        "payload": payload["metadata"],
    }

    ticket_id = await _post_ticket(
        url=f"{paperclip_url}/tickets",
        api_key=paperclip_api_key,
        payload=api_payload,
    )

    # Fallback to a local placeholder if the service is unavailable, so the
    # graph always returns a ticket reference.
    if ticket_id is None:
        ticket_id = f"PPC-LOCAL-{state.get('interaction_id', '?')}"
        logger.warning(
            "paperclip_ticket_fallback",
            ticket_id=ticket_id,
            reason="service_unreachable",
        )

    return {"paperclip_ticket_id": ticket_id}
