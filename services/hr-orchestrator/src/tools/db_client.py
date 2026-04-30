"""Database client for PostgreSQL logging (HR -- read-only, no proposals)."""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("hr-orchestrator.db")


class DBClient:
    """Async PostgreSQL client using asyncpg for logging interactions.

    HR is read-only: no log_proposal method.
    """

    def __init__(self, pool: Any) -> None:
        """Accept an asyncpg pool (or None for testing)."""
        self._pool = pool

    @property
    def pool(self) -> Any:
        """Expose pool for shared library nodes that need db_conn."""
        return self._pool

    async def create_interaction(
        self,
        user_id: str,
        channel: str,
        thread_ts: str | None,
        query: str,
    ) -> int | None:
        """INSERT minimal interaction row. Returns ID."""
        if self._pool is None:
            logger.warning("db_pool_unavailable", operation="create_interaction")
            return None
        sql = """
            INSERT INTO agent_interactions (user_id, channel, thread_ts, query)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        row = await self._pool.fetchrow(sql, user_id, channel, thread_ts, query)
        iid = row["id"] if row else None
        logger.info("interaction_created", id=iid)
        return iid

    async def update_interaction(
        self,
        interaction_id: int | None,
        intent: str | None = None,
        response: str | None = None,
        sources_count: int | None = None,
        escalation: bool = False,
        confidence: float | None = None,
        processing_ms: int | None = None,
        paperclip_ticket_id: str | None = None,
    ) -> None:
        """UPDATE interaction row with results."""
        if self._pool is None or interaction_id is None:
            return
        sql = """
            UPDATE agent_interactions
            SET intent = $2, response = $3, sources_count = $4,
                escalation = $5,
                confidence = $6, processing_ms = $7, paperclip_ticket_id = $8
            WHERE id = $1
        """
        await self._pool.execute(
            sql, interaction_id, intent, response, sources_count,
            escalation, confidence, processing_ms,
            paperclip_ticket_id,
        )
        logger.info("interaction_updated", id=interaction_id)

    async def log_escalation(
        self,
        interaction_id: int | None,
        severity: str,
        trigger_type: str,
        detail: str,
        paperclip_ticket_id: str | None = None,
    ) -> None:
        """INSERT into escalations."""
        if self._pool is None:
            logger.warning("db_pool_unavailable", operation="log_escalation")
            return
        sql = """
            INSERT INTO escalations
                (interaction_id, severity, trigger_type, detail, paperclip_ticket_id)
            VALUES ($1, $2, $3, $4, $5)
        """
        await self._pool.execute(
            sql,
            interaction_id,
            severity,
            trigger_type,
            detail,
            paperclip_ticket_id,
        )
        logger.info("escalation_logged", severity=severity, trigger_type=trigger_type)
