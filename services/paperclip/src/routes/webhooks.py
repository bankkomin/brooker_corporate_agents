"""Webhook endpoints for receiving events from other services."""
import json

import structlog
from fastapi import APIRouter, Depends

from src.auth import verify_webhook_auth
from src.db.connection import get_pool
from src.models import ApprovalWebhook
from src.services.event_router import EventRouter
from src.services.ticket_service import TicketService

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/approval", dependencies=[Depends(verify_webhook_auth)])
async def receive_approval(body: ApprovalWebhook):
    """Handle approval/rejection/deferral from approval-ui."""
    pool = await get_pool()
    ticket_svc = TicketService(pool)
    event_router = EventRouter()

    # Find the ticket for this proposal
    tickets = await ticket_svc.list_tickets(status="pending_approval")
    target = None
    for t in tickets:
        payload = t.get("payload", {})
        if isinstance(payload, str):
            payload = json.loads(payload)
        if payload.get("proposal_id") == body.proposal_id:
            target = t
            break

    if target is None:
        logger.warning("approval_webhook_no_ticket", proposal_id=body.proposal_id)
    else:
        status_map = {
            "approved": "completed",
            "rejected": "rejected",
            "deferred": "pending_approval",
        }
        new_status = status_map.get(body.decision, "open")
        await ticket_svc.update_ticket(target["ticket_id"], status=new_status)

    await event_router.route_approval(
        body.proposal_id, body.decision, body.reviewer, body.edited_values,
    )

    logger.info("approval_webhook_processed", proposal_id=body.proposal_id, decision=body.decision)
    return {"status": "processed", "decision": body.decision, "proposal_id": body.proposal_id}
