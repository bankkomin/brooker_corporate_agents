"""B5 — Draft per-dept daily-log staging entries from yesterday's session activity.

Runs as part of the nightly reflection job. For each live dept, builds a
markdown daily-log summary from:

- proposals created yesterday (from Postgres)
- approval decisions made yesterday (existing decisions_joiner)
- knowledge gaps surfaced (existing decisions_joiner)

Writes the draft to /data/staging/pending/ via the shared
`vault_staging.write_vault_staging` helper. The dept HOD reviews and
approves through approval-ui before sync-back writes to the actual
vault path `obsidian-vault/{dept}/daily-logs/YYYY-MM-DD.md`.

Never modifies vault files directly — staging-only by design.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import asyncpg

from .decisions_joiner import get_recent_decisions, get_recent_knowledge_gaps

try:  # services.shared is the canonical import path inside the monorepo
    from services.shared.vault_staging import build_manifest, write_vault_staging
except ImportError:  # pragma: no cover — fallback for in-service test runs
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from services.shared.vault_staging import build_manifest, write_vault_staging

log = logging.getLogger(__name__)


def render_daily_log_md(
    *,
    dept_id: str,
    target_date: date,
    decisions: list,
    gaps: list,
    proposal_count: int,
) -> str:
    """Render the daily-log body. Pure function, easy to test."""
    lines = [
        "---",
        f"date: {target_date.isoformat()}",
        "type: daily-log",
        f"department: {dept_id}",
        f"created: {datetime.utcnow().isoformat()}",
        "tags: [daily-log, automated, vault_automation]",
        "---",
        "",
        f"# Daily Log — {dept_id} — {target_date.isoformat()}",
        "",
        "## Summary",
        f"- Proposals created: {proposal_count}",
        f"- Approval decisions: {len(decisions)}",
        f"- Knowledge gaps surfaced: {len(gaps)}",
        "",
    ]
    if decisions:
        lines.append("## Approval decisions")
        for d in decisions:
            action = getattr(d, "action", "unknown")
            pid = getattr(d, "proposal_id", "?")
            signal = getattr(d, "signal_strength", 0.0)
            lines.append(f"- `{pid}` — {action} (signal={signal:.2f})")
        lines.append("")
    if gaps:
        lines.append("## Knowledge gaps")
        for g in gaps:
            agent = g.get("agent_id", "?") if isinstance(g, dict) else getattr(g, "agent_id", "?")
            query = g.get("query", "")[:120] if isinstance(g, dict) else getattr(g, "query", "")[:120]
            hits = g.get("hit_count", 0) if isinstance(g, dict) else getattr(g, "hit_count", 0)
            lines.append(f"- **{agent}** asked: \"{query}\" (matched {hits} chunks)")
        lines.append("")
    lines.extend([
        "## Source",
        "Drafted by `reflection-engine.daily_log_drafter` from yesterday's Postgres records.",
        "Review and edit before approval; sync-back will write this file to the dept's `daily-logs/` folder.",
        "",
    ])
    return "\n".join(lines)


async def _count_proposals(db_pool: asyncpg.Pool, dept_id: str, target_date: date) -> int:
    """Best-effort count of proposals created on target_date for this dept.

    Returns 0 if the proposals table or the dept column isn't present; this
    avoids a crash during early bootstrap before approval flows are wired.
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT count(*) AS n FROM proposals
                   WHERE dept_id = $1
                     AND created_at >= $2::date
                     AND created_at < ($2::date + INTERVAL '1 day')""",
                dept_id, target_date,
            )
            return int(row["n"]) if row else 0
    except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
        return 0
    except Exception:  # pragma: no cover — diagnostic only
        log.exception("daily_log_drafter._count_proposals failed for %s", dept_id)
        return 0


async def draft_daily_log(
    dept_id: str,
    db_pool: asyncpg.Pool,
    *,
    staging_path: str,
    target_date: date | None = None,
    source_run_id: str | None = None,
) -> str | None:
    """Build a daily-log markdown for `dept_id` and stage it. Returns proposal id."""
    target_date = target_date or (datetime.utcnow().date() - timedelta(days=1))

    decisions = await get_recent_decisions(db_pool, dept_id)
    gaps = await get_recent_knowledge_gaps(db_pool, dept_id)
    proposal_count = await _count_proposals(db_pool, dept_id, target_date)

    if not decisions and not gaps and proposal_count == 0:
        log.info("daily_log_drafter: no activity for %s on %s, skipping", dept_id, target_date)
        return None

    body = render_daily_log_md(
        dept_id=dept_id,
        target_date=target_date,
        decisions=decisions,
        gaps=gaps,
        proposal_count=proposal_count,
    )
    target = f"{dept_id}/daily-logs/{target_date.isoformat()}.md"
    manifest = build_manifest(
        agent="reflection-engine.daily_log_drafter",
        dept=dept_id,
        target_vault_path=target,
        operation="create",
        draft_content=body,
        confidence=0.9,  # mechanical aggregation, high deterministic confidence
        reasoning=(
            f"Aggregated {len(decisions)} approval decisions, "
            f"{len(gaps)} knowledge gaps, {proposal_count} proposals."
        ),
        source_run_id=source_run_id,
    )
    return await write_vault_staging(manifest, staging_path=staging_path)
