import logging
from dataclasses import dataclass
from typing import List

import asyncpg

log = logging.getLogger(__name__)


@dataclass
class EnrichedDecision:
    proposal_id: int
    agent_id: str
    action: str
    signal_strength: float
    rejection_reason: str | None = None
    edited_value: str | None = None


async def get_recent_decisions(db_pool: asyncpg.Pool, dept_id: str, days: int = 1) -> List[EnrichedDecision]:
    """Fetch recent approval decisions with computed signal_strength for a department."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT agent_id, proposal_id, action, signal_strength, rejection_reason, edited_value
            FROM agent_performance
            WHERE dept_id = $1 AND created_at > NOW() - make_interval(days => $2)
            ORDER BY created_at DESC
            """,
            dept_id, days,
        )
    return [
        EnrichedDecision(
            proposal_id=r["proposal_id"],
            agent_id=r["agent_id"],
            action=r["action"],
            signal_strength=float(r["signal_strength"]) if r["signal_strength"] is not None else 0.0,
            rejection_reason=r["rejection_reason"],
            edited_value=r["edited_value"],
        )
        for r in rows
    ]


async def get_recent_knowledge_gaps(db_pool: asyncpg.Pool, dept_id: str, days: int = 1) -> list[dict]:
    """Fetch unresolved knowledge gaps from the last N days."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT agent_id, query, hit_count, llm_self_report, expected_doc_type
            FROM agent_knowledge_gaps
            WHERE dept_id = $1 AND created_at > NOW() - make_interval(days => $2)
              AND resolved_at IS NULL
            ORDER BY created_at DESC
            """,
            dept_id, days,
        )
    return [dict(r) for r in rows]
