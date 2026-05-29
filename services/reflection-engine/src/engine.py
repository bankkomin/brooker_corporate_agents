"""Core reflection engine.

Orchestrates per-department reflection:
  1. Parse yesterday's daily log
  2. Fetch recent approval decisions + knowledge gaps from Postgres
  3. For each agent memory directory, call LLM to produce updates
  4. Promote durable facts into obsidian-vault/{dept}/_memory/ (memory.md / user.md)
  5. Write LLM-flagged skill improvement patterns to /data/staging/pending/skill-updates/
  6. Record run metadata in reflection_runs Postgres table

CRITICAL: this module NEVER writes to /data/mirror/.
  - obsidian-vault writes are inside the vault mount (read-write)
  - skill proposals go to /data/staging/pending/skill-updates/ only
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import structlog

from .config import settings
from .daily_log_drafter import draft_daily_log
from .decisions_joiner import get_recent_decisions, get_recent_knowledge_gaps
from .log_reader import parse_daily_log
from .pattern_detector import detect_skill_improvement_patterns
from .promoter import promote_memory
from .sdk_client import run_reflection_llm
from .skill_proposal_writer import write_skill_proposals

log = structlog.get_logger(__name__)


async def run_dept_reflection(
    dept_id: str,
    db_pool: asyncpg.Pool,
    *,
    dry_run: bool = False,
    date_override: str | None = None,
) -> dict:
    """Run the full reflection cycle for a single department.

    Args:
        dept_id: Short department identifier (e.g. "cac", "hr").
        db_pool: asyncpg connection pool.
        dry_run: If True, skips LLM calls and file writes.
        date_override: YYYY-MM-DD to read instead of yesterday (testing).

    Returns:
        Summary dict with counts and per-agent change details.
    """
    run_id = await _start_run(db_pool, dept_id)
    result: dict = {
        "dept_id": dept_id,
        "run_id": run_id,
        "dry_run": dry_run,
        "agents_processed": 0,
        "changes": [],
        "skill_proposals_written": 0,
    }
    logger = log.bind(dept=dept_id, run_id=run_id, dry_run=dry_run)

    try:
        vault_root = Path(settings.VAULT_ROOT)
        dept_vault = vault_root / dept_id

        # ── 1. Read yesterday's daily log ───────────────────────────────────
        if date_override:
            log_date = date_override
        else:
            log_date = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        log_path = dept_vault / "daily-logs" / f"{log_date}.md"
        entries = parse_daily_log(log_path)
        daily_log_text = (
            "\n".join(
                f"- [{e.timestamp}] @{e.user_id}: Q={e.query[:100]} "
                f"| outcome={e.outcome} | conf={e.confidence:.2f}"
                for e in entries
            )
            or "(no entries)"
        )
        logger.info("daily_log_read", date=log_date, entry_count=len(entries))

        # ── 2. Fetch decisions + knowledge gaps ─────────────────────────────
        try:
            decisions = await get_recent_decisions(db_pool, dept_id)
            gaps = await get_recent_knowledge_gaps(db_pool, dept_id)
        except Exception:
            logger.warning("db_fetch_failed_using_empty", exc_info=True)
            decisions = []
            gaps = []

        decisions_text = (
            "\n".join(
                f"- proposal {d.proposal_id}: {d.action} (signal={d.signal_strength:.2f})"
                for d in decisions
            )
            or "(no decisions)"
        )
        gaps_text = (
            "\n".join(
                f"- {g.get('agent_id', '?')}: '{str(g.get('query', ''))[:80]}' (hits={g.get('hit_count', 0)})"
                for g in gaps
            )
            or "(no gaps)"
        )

        # ── 3. Per-agent loop ────────────────────────────────────────────────
        memory_root = dept_vault / "_memory"
        if not memory_root.exists():
            logger.info("no_memory_dir_skipping")
            await _complete_run(db_pool, run_id, "success", stats=result)
            return result

        agent_dirs = [
            d for d in memory_root.iterdir()
            if d.is_dir() and d.name != "history"
        ]
        logger.info("agents_found", count=len(agent_dirs))

        all_llm_skill_proposals: list[dict] = []

        for agent_dir in agent_dirs:
            agent_id = agent_dir.name
            memory_file = agent_dir / "memory.md"
            user_file = agent_dir / "user.md"

            current_memory = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
            current_user = user_file.read_text(encoding="utf-8") if user_file.exists() else ""

            if dry_run:
                result["agents_processed"] += 1
                result["changes"].append({"agent_id": agent_id, "action": "dry_run"})
                continue

            # ── 4. LLM reflection ────────────────────────────────────────────
            sdk_output = await run_reflection_llm(
                dept_id=dept_id,
                agent_id=agent_id,
                daily_log=daily_log_text,
                decisions=decisions_text,
                gaps=gaps_text,
                current_memory=current_memory,
                current_user=current_user,
            )

            # ── 5. Promote memory updates ────────────────────────────────────
            changes = promote_memory(agent_dir, sdk_output)
            result["agents_processed"] += 1
            result["changes"].append({"agent_id": agent_id, **changes})

            # Collect LLM-flagged skill proposals for this agent
            for sp in sdk_output.get("skill_proposals", []):
                sp["agent_id"] = agent_id
                all_llm_skill_proposals.append(sp)

        # ── 6. Pattern-based skill proposals (from DB) ──────────────────────
        try:
            db_proposals = await detect_skill_improvement_patterns(db_pool, dept_id)
        except Exception:
            logger.warning("pattern_detection_failed", exc_info=True)
            db_proposals = []

        # ── 7. Write skill proposals to staging ─────────────────────────────
        if not dry_run:
            # DB-sourced proposals
            for prop in db_proposals:
                written = write_skill_proposals(
                    dept_id=dept_id,
                    agent_id=prop.get("agent_id", "unknown"),
                    proposals=[prop],
                )
                result["skill_proposals_written"] += len(written)

            # LLM-flagged proposals (grouped by agent)
            from itertools import groupby
            all_llm_skill_proposals.sort(key=lambda x: x.get("agent_id", ""))
            for agent_id, group_iter in groupby(all_llm_skill_proposals, key=lambda x: x.get("agent_id", "")):
                written = write_skill_proposals(
                    dept_id=dept_id,
                    agent_id=agent_id,
                    proposals=list(group_iter),
                )
                result["skill_proposals_written"] += len(written)

        result["db_skill_proposals_detected"] = len(db_proposals)

        # ── 8. B5: Draft a daily-log staging entry for yesterday's activity.
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
                logger.exception("daily_log_drafter_failed", dept=dept_id)
                result["daily_log_proposal_id"] = None

        logger.info("reflection_complete", **{k: v for k, v in result.items() if k != "changes"})
        await _complete_run(db_pool, run_id, "success", stats=result)

    except Exception:
        logger.exception("reflection_failed")
        error_msg = "reflection cycle failed — see logs"
        await _complete_run(db_pool, run_id, "failed", error=error_msg)
        result["error"] = error_msg

    return result


# ── DB helpers ───────────────────────────────────────────────────────────────

async def _start_run(db_pool: asyncpg.Pool, dept_id: str) -> int:
    """Insert a reflection_runs row and return its id.

    Degrades gracefully: returns -1 if the DB is unavailable.
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO reflection_runs (dept_id, started_at, status)
                   VALUES ($1, NOW(), 'running') RETURNING id""",
                dept_id,
            )
            return int(row["id"])
    except Exception:
        log.warning("reflection_runs_insert_failed", dept=dept_id, exc_info=True)
        return -1


async def _complete_run(
    db_pool: asyncpg.Pool,
    run_id: int,
    status: str,
    error: str | None = None,
    stats: dict | None = None,
) -> None:
    """Update the reflection_runs row on completion.

    No-ops if run_id == -1 (DB was unavailable at start).
    """
    if run_id == -1:
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE reflection_runs
                   SET completed_at = NOW(), status = $2, error = $3, stats = $4::jsonb
                   WHERE id = $1""",
                run_id,
                status,
                error,
                json.dumps(stats) if stats else None,
            )
    except Exception:
        log.warning("reflection_runs_update_failed", run_id=run_id, exc_info=True)
