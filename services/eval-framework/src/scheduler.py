import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .golden_loader import load_golden_answers
from .runner import run_eval

logger = logging.getLogger(__name__)

DEPARTMENTS = ["cac", "hr"]


async def _nightly_eval(db_pool) -> None:
    """Run evaluations for all registered departments."""
    for dept_id in DEPARTMENTS:
        logger.info("Starting nightly eval for %s", dept_id)
        golden = load_golden_answers(dept_id)
        if not golden:
            logger.warning("No golden answers found for %s, skipping", dept_id)
            continue
        try:
            summary = await run_eval(dept_id, golden, db_pool)
            logger.info(
                "Eval complete for %s: accuracy=%.1f%% (%d/%d)",
                dept_id,
                summary["accuracy"] * 100,
                summary["passed"],
                summary["total"],
            )
        except Exception:
            logger.exception("Eval failed for %s", dept_id)


def start_scheduler(db_pool) -> AsyncIOScheduler:
    """Start the APScheduler with a nightly eval job at 03:00."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        _nightly_eval,
        trigger=CronTrigger(hour=3, minute=0),
        args=[db_pool],
        id="nightly_eval",
        name="Nightly evaluation run (after reflection engine at 02:00)",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Eval scheduler started - nightly run at 03:00")
    return scheduler
