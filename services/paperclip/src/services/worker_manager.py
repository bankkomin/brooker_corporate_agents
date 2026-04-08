"""Worker management for Paperclip — OpenClaw stub implementation."""
import asyncpg
import structlog

from src.db import queries

logger = structlog.get_logger()


class WorkerManager:
    """Manages worker agents (OpenClaw stub for now)."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def assign_ticket(self, worker_name: str, ticket_id: str) -> dict:
        """Assign a ticket to a worker agent."""
        async with self._pool.acquire() as conn:
            agent = await conn.fetchrow(
                "SELECT worker_type, status FROM paperclip_agents WHERE agent_name = $1",
                worker_name,
            )
            if agent is None:
                raise ValueError(f"Worker '{worker_name}' not found")
            if agent["status"] != "active":
                raise ValueError(f"Worker '{worker_name}' not active (status: {agent['status']})")

            target_status = "pending_human" if agent["worker_type"] == "stub" else "in_progress"

            row = await conn.fetchrow(
                queries.UPDATE_TICKET,
                ticket_id, target_status, None, worker_name,
            )
            if row is None:
                raise ValueError(f"Ticket '{ticket_id}' not found")

            logger.info(
                "ticket_assigned_to_worker",
                ticket_id=ticket_id, worker=worker_name,
                worker_type=agent["worker_type"], status=target_status,
            )
            return dict(row)

    async def get_worker_status(self, worker_name: str) -> dict:
        """Get worker status and assigned tickets."""
        async with self._pool.acquire() as conn:
            agent = await conn.fetchrow(
                "SELECT agent_name, worker_type, status"
                " FROM paperclip_agents WHERE agent_name = $1",
                worker_name,
            )
            if agent is None:
                raise ValueError(f"Worker '{worker_name}' not found")

            tickets = await conn.fetch(
                "SELECT ticket_id, status, type FROM paperclip_tickets"
                " WHERE assigned_worker = $1"
                " AND status NOT IN ('completed', 'failed')",
                worker_name,
            )
            return {
                **dict(agent),
                "assigned_tickets": [dict(t) for t in tickets],
            }
