import logging
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .synthesis_scan_trigger import trigger_synthesis_scan
from .vault_health_check import run_and_persist as run_vault_health_check

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
    log.info("Reflection scheduler started: %02d:%02d daily", settings.REFLECTION_CRON_HOUR, settings.REFLECTION_CRON_MINUTE)
    if settings.VAULT_HEALTH_CHECK_ENABLED:
        scheduler.add_job(
            _run_vault_health_check_job,
            "cron",
            hour=settings.VAULT_HEALTH_CHECK_CRON_HOUR,
            minute=settings.VAULT_HEALTH_CHECK_CRON_MINUTE,
            id="vault_health_check",
            replace_existing=True,
        )
        log.info(
            "Vault health check scheduled: %02d:%02d daily",
            settings.VAULT_HEALTH_CHECK_CRON_HOUR,
            settings.VAULT_HEALTH_CHECK_CRON_MINUTE,
        )
    if settings.SYNTHESIS_SCAN_ENABLED:
        scheduler.add_job(
            _run_synthesis_scan_job,
            "cron",
            hour=settings.SYNTHESIS_SCAN_CRON_HOUR,
            minute=settings.SYNTHESIS_SCAN_CRON_MINUTE,
            id="nightly_synthesis_scan",
            replace_existing=True,
        )
        log.info(
            "Synthesis scan scheduled: %02d:%02d daily -> %s",
            settings.SYNTHESIS_SCAN_CRON_HOUR,
            settings.SYNTHESIS_SCAN_CRON_MINUTE,
            settings.RAG_INGESTION_URL,
        )
    scheduler.start()
    return scheduler


async def _run_vault_health_check_job() -> None:
    """Wraps run_vault_health_check with exception isolation."""
    try:
        await run_vault_health_check(Path(settings.VAULT_ROOT))
    except Exception:
        log.exception("Vault health check failed")


async def _run_synthesis_scan_job() -> None:
    """Wraps trigger_synthesis_scan with exception isolation."""
    try:
        await trigger_synthesis_scan(
            rag_ingestion_url=settings.RAG_INGESTION_URL,
            timeout_seconds=settings.SYNTHESIS_SCAN_TIMEOUT,
        )
    except Exception:
        log.exception("Synthesis scan trigger failed")


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
