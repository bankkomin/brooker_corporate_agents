"""Department and agent registry management."""
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
        elif isinstance(v, str) and k in ("data_zone", "escalation_rules", "config", "skills", "data_scope", "permissions"):
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        else:
            result[k] = v
    return result


class DepartmentService:
    """Manages departments and their agent registrations."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def create_department(
        self, name: str, display_name: str, slack_channel: str,
        hod_email: str, data_zone: dict,
        escalation_rules: dict | None = None, config: dict | None = None,
    ) -> dict:
        """Register a new department."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                queries.CREATE_DEPARTMENT,
                name, display_name, slack_channel, hod_email,
                json.dumps(escalation_rules or {}),
                json.dumps(data_zone),
                json.dumps(config or {}),
            )
            logger.info("department_created", name=name)
            return _serialize_row(dict(row))

    async def list_departments(self) -> list[dict]:
        """List all departments with agent counts."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(queries.LIST_DEPARTMENTS)
            return [_serialize_row(dict(r)) for r in rows]

    async def get_department(self, name: str) -> dict | None:
        """Get department by name."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(queries.GET_DEPARTMENT, name)
            return _serialize_row(dict(row)) if row else None

    async def register_agent(
        self, department: str, agent_name: str, agent_role: str,
        worker_type: str | None = None, endpoint_url: str | None = None,
        skills: list[str] | None = None, data_scope: dict | None = None,
        permissions: dict | None = None,
    ) -> dict:
        """Register or update an agent in a department."""
        async with self._pool.acquire() as conn:
            dept_id = await conn.fetchval(queries.GET_DEPARTMENT_ID, department)
            if dept_id is None:
                raise ValueError(f"Department '{department}' not found")

            row = await conn.fetchrow(
                queries.REGISTER_AGENT,
                dept_id, agent_name, agent_role, worker_type, endpoint_url,
                json.dumps(skills or []),
                json.dumps(data_scope or {}),
                json.dumps(permissions or {}),
            )
            logger.info("agent_registered", agent=agent_name, department=department)
            return dict(row)

    async def list_agents(self, department: str) -> list[dict]:
        """List agents in a department."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(queries.LIST_AGENTS, department)
            return [dict(r) for r in rows]

    async def deregister_agent(self, department: str, agent_name: str) -> bool:
        """Mark an agent as inactive."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(queries.DEREGISTER_AGENT, department, agent_name)
            if row:
                logger.info("agent_deregistered", agent=agent_name, department=department)
            return row is not None
