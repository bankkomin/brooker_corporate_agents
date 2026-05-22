import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings

log = logging.getLogger(__name__)


def start_scheduler(db_pool) -> AsyncIOScheduler:
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
    log.info("Reflection scheduler started: %02d:%02d daily", settings.REFLECTION_CRON_HOUR, settings.REFLECTION_CRON_MINUTE)
    return scheduler


async def _run_all_live_depts(db_pool):
    """Run reflection for every live department."""
    import json
    from pathlib import Path

    from .engine import run_dept_reflection

    config_path = Path("/app/config/departments.json")
    if not config_path.exists():
        log.warning("departments.json not found at %s", config_path)
        return

    data = json.loads(config_path.read_text())
    departments = data.get("departments", [])
    if isinstance(departments, dict):
        dept_list = [{"dept_id": k, **v} for k, v in departments.items()]
    else:
        dept_list = departments

    for dept in dept_list:
        if not dept.get("live", False):
            continue
        dept_id = dept.get("dept_id", dept.get("shortName", "unknown"))
        try:
            await run_dept_reflection(dept_id, db_pool)
            log.info("Reflection complete for %s", dept_id)
        except Exception:
            log.exception("Reflection failed for %s", dept_id)
