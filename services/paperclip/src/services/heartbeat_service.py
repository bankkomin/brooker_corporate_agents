"""Heartbeat monitoring for registered agents."""
import asyncpg
import structlog

from src.db import queries

logger = structlog.get_logger()


class HeartbeatService:
    """Monitors agent health via heartbeat registrations."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def update_heartbeat(self, agent_name: str, department: str) -> dict:
        """Update heartbeat timestamp for an agent."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(queries.UPDATE_HEARTBEAT, agent_name, department)
            if row is None:
                raise ValueError(f"Agent '{agent_name}' not found in department '{department}'")
            logger.info("heartbeat_updated", agent=agent_name, department=department)
            return dict(row)

    async def list_heartbeats(self) -> list[dict]:
        """List all active agents with health status."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(queries.LIST_HEARTBEATS)
            return [dict(r) for r in rows]

    async def mark_stale_agents(self) -> list[str]:
        """Mark agents with expired heartbeats as inactive."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(queries.MARK_STALE_AGENTS)
            stale = [r["agent_name"] for r in rows]
            if stale:
                logger.warning("stale_agents_marked", agents=stale)
            return stale
