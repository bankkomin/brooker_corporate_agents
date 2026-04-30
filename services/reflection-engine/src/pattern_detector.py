import json
import logging
from typing import List

import asyncpg

from .config import settings

log = logging.getLogger(__name__)


async def detect_skill_improvement_patterns(
    db_pool: asyncpg.Pool,
    dept_id: str,
    threshold_count: int | None = None,
    signal_max: float | None = None,
) -> List[dict]:
    """Detect skills with repeated low-signal corrections.

    Returns list of skill proposals when:
    - >= threshold_count same-shape interactions in last 7 days
    - Average signal_strength < signal_max
    """
    if threshold_count is None:
        threshold_count = settings.MIN_PATTERN_COUNT
    if signal_max is None:
        signal_max = settings.SIGNAL_THRESHOLD

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ap.dept_id,
                ai.agent_id,
                COUNT(*) AS n,
                AVG(ap.signal_strength) AS avg_signal
            FROM agent_performance ap
            JOIN agent_interactions ai ON ai.id = (
                SELECT sp2.interaction_id FROM staging_proposals sp2 WHERE sp2.id = ap.proposal_id
            )
            WHERE ap.dept_id = $1
              AND ap.created_at > NOW() - INTERVAL '7 days'
            GROUP BY ap.dept_id, ai.agent_id
            HAVING COUNT(*) >= $2 AND AVG(ap.signal_strength) < $3
            """,
            dept_id, threshold_count, signal_max,
        )

        proposals = []
        for r in rows:
            proposal = {
                "dept_id": r["dept_id"],
                "agent_id": r["agent_id"],
                "trigger": f"avg signal {r['avg_signal']:.2f} over {r['n']} interactions in 7d",
                "evidence": {"count": r["n"], "avg_signal": float(r["avg_signal"])},
            }

            # Rate limit: 1 proposal per agent per week
            existing = await conn.fetchval(
                """SELECT COUNT(*) FROM agent_skill_proposals
                   WHERE dept_id = $1 AND agent_id = $2
                     AND created_at > NOW() - INTERVAL '7 days'""",
                r["dept_id"], r["agent_id"],
            )
            if existing and existing > 0:
                log.info("Skipping proposal for %s/%s — already proposed this week", r["dept_id"], r["agent_id"])
                continue

            # Insert into agent_skill_proposals table
            await conn.execute(
                """
                INSERT INTO agent_skill_proposals (dept_id, agent_id, skill_path, trigger, evidence)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                """,
                r["dept_id"],
                r["agent_id"],
                f"skills/{dept_id}/",  # exact skill_path resolved later by OpenClaw
                proposal["trigger"],
                json.dumps(proposal["evidence"]),
            )
            proposals.append(proposal)

        return proposals
