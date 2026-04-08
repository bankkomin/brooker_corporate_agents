"""Ticket CRUD endpoints."""
from fastapi import APIRouter, HTTPException

from src.db.connection import get_pool
from src.models import TicketCreate, TicketResponse, TicketUpdate
from src.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(body: TicketCreate):
    pool = await get_pool()
    svc = TicketService(pool)
    try:
        row = await svc.create_ticket(
            type=body.type, department=body.department,
            agent=body.agent, interaction_id=body.interaction_id,
            payload=body.payload,
        )
        return row
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str):
    pool = await get_pool()
    svc = TicketService(pool)
    row = await svc.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return row


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    department: str | None = None,
    type: str | None = None,
    status: str | None = None,
    agent: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    pool = await get_pool()
    svc = TicketService(pool)
    return await svc.list_tickets(department, type, status, agent, limit, offset)


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: str, body: TicketUpdate):
    pool = await get_pool()
    svc = TicketService(pool)
    row = await svc.update_ticket(
        ticket_id, status=body.status, result=body.result,
        assigned_worker=body.assigned_worker,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return row
