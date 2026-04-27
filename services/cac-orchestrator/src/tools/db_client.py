"""Database client for PostgreSQL logging."""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("cac-orchestrator.db")


class DBClient:
    """Async PostgreSQL client using asyncpg for logging interactions and proposals."""

    def __init__(self, pool: Any) -> None:
        """Accept an asyncpg pool (or None for testing)."""
        self._pool = pool

    async def create_interaction(
        self,
        user_id: str,
        channel: str,
        thread_ts: str | None,
        query: str,
    ) -> int | None:
        """INSERT minimal interaction row (Phase 1). Returns ID."""
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
        staging_proposal_id: str | None = None,
        confidence: float | None = None,
        processing_ms: int | None = None,
        paperclip_ticket_id: str | None = None,
    ) -> None:
        """UPDATE interaction row with results (Phase 2)."""
        if self._pool is None or interaction_id is None:
            return
        sql = """
            UPDATE agent_interactions
            SET intent = $2, response = $3, sources_count = $4,
                escalation = $5, staging_proposal_id = $6,
                confidence = $7, processing_ms = $8, paperclip_ticket_id = $9
            WHERE id = $1
        """
        await self._pool.execute(
            sql, interaction_id, intent, response, sources_count,
            escalation, staging_proposal_id, confidence, processing_ms,
            paperclip_ticket_id,
        )
        logger.info("interaction_updated", id=interaction_id)

    async def log_interaction(
        self,
        user_id: str,
        channel: str,
        thread_ts: str | None,
        query: str,
        intent: str | None = None,
        response: str | None = None,
        sources_count: int | None = None,
        escalation: bool = False,
        staging_proposal_id: str | None = None,
        confidence: float | None = None,
        processing_ms: int | None = None,
        paperclip_ticket_id: str | None = None,
    ) -> int | None:
        """INSERT into agent_interactions and return the row ID.

        Deprecated: Use create_interaction() + update_interaction() instead.
        Kept for backward compatibility.
        """
        if self._pool is None:
            logger.warning("db_pool_unavailable", operation="log_interaction")
            return None
        sql = """
            INSERT INTO agent_interactions
                (user_id, channel, thread_ts, query, intent, response,
                 sources_count, escalation, staging_proposal_id,
                 confidence, processing_ms, paperclip_ticket_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
        """
        row = await self._pool.fetchrow(
            sql,
            user_id,
            channel,
            thread_ts,
            query,
            intent,
            response,
            sources_count,
            escalation,
            staging_proposal_id,
            confidence,
            processing_ms,
            paperclip_ticket_id,
        )
        logger.info("interaction_logged", id=row["id"] if row else None)
        return row["id"] if row else None

    async def log_proposal(
        self,
        proposal_id: str,
        agent: str,
        file: str,
        tab: str,
        cell: str,
        old_value: str | None,
        new_value: str,
        source: str,
        confidence: float,
        reasoning: str,
        interaction_id: int | None = None,
        dept: str = "cac",
    ) -> None:
        """INSERT into staging_proposals.

        The `dept` column was added in migration 003_dept_columns.sql with a
        NOT NULL DEFAULT 'cac' constraint. Passing it explicitly lets callers
        scope proposals to the correct department at write time.
        """
        if self._pool is None:
            logger.warning("db_pool_unavailable", operation="log_proposal")
            return
        sql = """
            INSERT INTO staging_proposals
                (id, agent, file, tab, cell, old_value, new_value,
                 source, confidence, reasoning, status, interaction_id, dept)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending', $11, $12)
        """
        await self._pool.execute(
            sql,
            proposal_id,
            agent,
            file,
            tab,
            cell,
            old_value,
            new_value,
            source,
            confidence,
            reasoning,
            interaction_id,
            dept,
        )
        logger.info("proposal_logged", id=proposal_id, dept=dept)

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

    async def get_recent_proposals_for_cell(
        self, file: str, tab: str, cell: str, days: int = 7
    ) -> list[dict]:
        """Query staging_proposals for same cell in last N days (for validation cross-check)."""
        if self._pool is None:
            return []
        sql = """
            SELECT id, created_at, agent, old_value, new_value, confidence, reasoning, status
            FROM staging_proposals
            WHERE file = $1 AND tab = $2 AND cell = $3
              AND created_at > NOW() - INTERVAL '1 day' * $4
            ORDER BY created_at DESC
        """
        rows = await self._pool.fetch(sql, file, tab, cell, days)
        return [dict(row) for row in rows]
