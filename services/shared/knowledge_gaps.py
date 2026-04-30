"""Knowledge gap detection from LLM self-report phrases."""
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

SELF_REPORT_PATTERNS = [
    r"don'?t have data on",
    r"unable to find",
    r"no information about",
    r"i couldn'?t find",
    r"no relevant (data|documents|information)",
    r"insufficient data",
    r"not enough information",
]


async def detect_self_report(
    response: str,
    dept_id: str,
    agent_id: str,
    query: str,
    db_conn: Any,
) -> bool:
    """Check if the LLM response indicates a knowledge gap and log it.

    Returns True if a gap was detected and logged.
    """
    if not any(re.search(p, response, re.IGNORECASE) for p in SELF_REPORT_PATTERNS):
        return False

    try:
        await db_conn.execute(
            """INSERT INTO agent_knowledge_gaps
               (dept_id, agent_id, query, hit_count, llm_self_report)
               VALUES ($1, $2, $3, $4, $5)""",
            dept_id,
            agent_id,
            query[:500],
            0,
            response[:500],
        )
        log.info("Knowledge gap detected for %s/%s: %s", dept_id, agent_id, query[:80])
        return True
    except Exception:
        log.exception("Failed to write LLM self-report knowledge gap")
        return False
