import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg

from .config import settings
from .daily_log_drafter import draft_daily_log
from .decisions_joiner import get_recent_decisions, get_recent_knowledge_gaps
from .log_reader import parse_daily_log
from .pattern_detector import detect_skill_improvement_patterns
from .promoter import promote_memory
from .sdk_client import run_reflection_llm

log = logging.getLogger(__name__)


async def run_dept_reflection(dept_id: str, db_pool: asyncpg.Pool, dry_run: bool = False) -> dict:
    """Run the full reflection cycle for a department."""
    run_id = await _start_run(db_pool, dept_id)
    result = {"dept_id": dept_id, "run_id": run_id, "agents_processed": 0, "changes": []}

    try:
        vault_root = Path(settings.VAULT_ROOT)
        dept_vault = vault_root / dept_id

        # 1. Read yesterday's daily log
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        log_path = dept_vault / "daily-logs" / f"{yesterday}.md"
        entries = parse_daily_log(log_path)
        daily_log_text = "\n".join(
            f"- [{e.timestamp}] @{e.user_id}: Q={e.query[:100]} → outcome={e.outcome}"
            for e in entries
        ) or "(no entries yesterday)"

        # 2. Get approval decisions
        decisions = await get_recent_decisions(db_pool, dept_id)
        decisions_text = "\n".join(
            f"- proposal {d.proposal_id}: {d.action} (signal={d.signal_strength:.2f})"
            for d in decisions
        ) or "(no decisions)"

        # 3. Get knowledge gaps
        gaps = await get_recent_knowledge_gaps(db_pool, dept_id)
        gaps_text = "\n".join(
            f"- {g['agent_id']}: '{g['query'][:80]}' (hits={g['hit_count']})"
            for g in gaps
        ) or "(no gaps)"

        # 4. Process each agent in the department
        memory_root = dept_vault / "_memory"
        if not memory_root.exists():
            log.info("No _memory dir for %s, skipping", dept_id)
            await _complete_run(db_pool, run_id, "success", stats=result)
            return result

        for agent_dir in memory_root.iterdir():
            if not agent_dir.is_dir() or agent_dir.name == "history":
                continue

            agent_id = agent_dir.name
            memory_file = agent_dir / "memory.md"
            user_file = agent_dir / "user.md"

            current_memory = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
            current_user = user_file.read_text(encoding="utf-8") if user_file.exists() else ""

            if dry_run:
                result["agents_processed"] += 1
                result["changes"].append({"agent_id": agent_id, "action": "dry_run"})
                continue

            # 5. Call LLM for reflection
            sdk_output = await run_reflection_llm(
                dept_id=dept_id,
                agent_id=agent_id,
                daily_log=daily_log_text,
                decisions=decisions_text,
                gaps=gaps_text,
                current_memory=current_memory,
                current_user=current_user,
            )

            # 6. Promote memory updates
            changes = promote_memory(agent_dir, sdk_output)
            result["agents_processed"] += 1
            result["changes"].append({"agent_id": agent_id, **changes})

        # 7. Detect skill improvement patterns
        proposals = await detect_skill_improvement_patterns(db_pool, dept_id)
        result["skill_proposals"] = len(proposals)

        # 8. B5: Draft a daily-log staging entry for yesterday's activity.
        # The daily-log file lands in /data/staging/pending/ for HOD review.
        if settings.DAILY_LOG_DRAFTING_ENABLED and not dry_run:
            try:
                daily_log_proposal_id = await draft_daily_log(
                    dept_id, db_pool,
                    staging_path=settings.STAGING_PATH,
                    source_run_id=f"reflection_run_{run_id}",
                )
                result["daily_log_proposal_id"] = daily_log_proposal_id
            except Exception:
                log.exception("daily_log_drafter failed for %s", dept_id)
                result["daily_log_proposal_id"] = None

        await _complete_run(db_pool, run_id, "success", stats=result)

    except Exception as e:
        log.exception("Reflection failed for %s", dept_id)
        await _complete_run(db_pool, run_id, "failed", error=str(e))
        result["error"] = str(e)

    return result


async def _start_run(db_pool: asyncpg.Pool, dept_id: str) -> int:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO reflection_runs (dept_id, started_at, status)
               VALUES ($1, NOW(), 'running') RETURNING id""",
            dept_id,
        )
        return row["id"]


async def _complete_run(db_pool: asyncpg.Pool, run_id: int, status: str, error: str | None = None, stats: dict | None = None):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """UPDATE reflection_runs
               SET completed_at = NOW(), status = $2, error = $3, stats = $4::jsonb
               WHERE id = $1""",
            run_id, status, error, json.dumps(stats) if stats else None,
        )
