"""Paperclip ticket stub — placeholder until Stage 7."""
from __future__ import annotations

import itertools

import structlog

logger = structlog.get_logger("cac-orchestrator.paperclip")

# Thread-safe counter (itertools.count is atomic)
_ticket_counter = itertools.count(1)


async def create_paperclip_ticket(state: dict) -> dict:
    """Create a Paperclip ticket (stub).

    Returns {"paperclip_ticket_id": str}.
    Real Paperclip integration will be implemented in Stage 7.
    """
    ticket_id = f"PPC-{next(_ticket_counter):04d}"

    logger.info(
        "paperclip_ticket_stub",
        ticket_id=ticket_id,
        query=state.get("query", "")[:100],
        intent=state.get("intent", ""),
        has_proposal=state.get("staging_proposal_id") is not None,
    )
    return {"paperclip_ticket_id": ticket_id}
