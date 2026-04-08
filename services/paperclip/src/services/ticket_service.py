"""Ticket management business logic."""
import json
from uuid import UUID

import asyncpg
import structlog

from src.db import queries

logger = structlog.get_logger()


def _serialize_row(row: dict) -> dict:
    """Convert asyncpg types (UUID, JSONB strings) to Python natives."""
    result = {}
    for k, v in row.items():
        if isinstance(v, UUID):
            result[k] = str(v)
        elif isinstance(v, str) and k in ("payload", "result"):
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        else:
            result[k] = v
    return result


class TicketService:
    """Manages Paperclip ticket lifecycle."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create_ticket(
        self,
        type: str,
        department: str,
        agent: str,
        interaction_id: str | None,
        payload: dict,
    ) -> dict:
        """Create a new ticket with sequential PPC-XXXX ID."""
        async with self._pool.acquire() as conn:
            # Validate department exists
            dept_id = await conn.fetchval(queries.GET_DEPARTMENT_ID, department)
            if dept_id is None:
                raise ValueError(f"Department '{department}' not found")

            # Generate sequential ticket ID
            next_num = await conn.fetchval(queries.NEXT_TICKET_ID)
            ticket_id = f"PPC-{next_num:04d}"

            row = await conn.fetchrow(
                queries.CREATE_TICKET,
                ticket_id, type, department, agent, interaction_id,
                json.dumps(payload),
            )
            logger.info("ticket_created", ticket_id=ticket_id, type=type, department=department)
            return _serialize_row(dict(row))

    async def get_ticket(self, ticket_id: str) -> dict | None:
        """Get a ticket by its PPC-XXXX ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(queries.GET_TICKET, ticket_id)
            return _serialize_row(dict(row)) if row else None

    async def list_tickets(
        self,
        department: str | None = None,
        type: str | None = None,
        status: str | None = None,
        agent: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List tickets with optional filters."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                queries.LIST_TICKETS,
                department, type, status, agent, limit, offset,
            )
            return [_serialize_row(dict(r)) for r in rows]

    async def update_ticket(
        self,
        ticket_id: str,
        status: str | None = None,
        result: dict | None = None,
        assigned_worker: str | None = None,
    ) -> dict | None:
        """Update ticket fields."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                queries.UPDATE_TICKET,
                ticket_id, status,
                json.dumps(result) if result else None,
                assigned_worker,
            )
            if row:
                logger.info("ticket_updated", ticket_id=ticket_id, status=status)
            return _serialize_row(dict(row)) if row else None
