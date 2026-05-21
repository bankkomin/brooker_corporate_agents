"""APScheduler cron wrapper for nightly reflection.

Fires at REFLECTION_CRON_HOUR:REFLECTION_CRON_MINUTE (default 02:00 UTC).

If APScheduler is unavailable or the DB is None, we skip without crashing —
the /reflect/all HTTP endpoint can be used as a fallback from an external cron.
"""
from __future__ import annotations

import json
from pathlib import Path

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings

log = structlog.get_logger(__name__)


def start_scheduler(db_pool) -> AsyncIOScheduler:
    """Create and start an AsyncIOScheduler with the nightly reflection job."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_all_live_depts,
        "cron",
        hour=settings.REFLECTION_CRON_HOUR,
        minute=settings.REFLECTION_CRON_MINUTE,
        kwargs={"db_pool": db_pool},
        id="nightly_reflection",
        replace_existing=True,
    )
    scheduler.start()
    log.info(
        "scheduler_started",
        cron_hour=settings.REFLECTION_CRON_HOUR,
        cron_minute=settings.REFLECTION_CRON_MINUTE,
    )
    return scheduler


async def _run_all_live_depts(db_pool) -> None:
    """Nightly job: reflect over every live department in departments.json."""
    from .engine import run_dept_reflection

    config_path = Path("/app/config/departments.json")
    if not config_path.exists():
        log.warning("departments_json_not_found", path=str(config_path))
        return

    data = json.loads(config_path.read_text(encoding="utf-8"))
    departments = data.get("departments", [])
    if isinstance(departments, dict):
        dept_list = [{"dept_id": k, **v} for k, v in departments.items()]
    else:
        dept_list = departments

    live = [d for d in dept_list if d.get("live", False)]
    log.info("nightly_reflection_starting", live_dept_count=len(live))

    for dept in live:
        dept_id: str = str(dept.get("dept_id", dept.get("shortName", "unknown")))
        try:
            result = await run_dept_reflection(dept_id, db_pool)
            log.info(
                "nightly_reflection_dept_done",
                dept=dept_id,
                agents=result.get("agents_processed", 0),
                skill_proposals=result.get("skill_proposals_written", 0),
            )
        except Exception:
            log.exception("nightly_reflection_dept_failed", dept=dept_id)
