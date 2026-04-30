import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .context_gatherer import gather_context
from .orchestrator_client import invoke_proactive

log = logging.getLogger(__name__)


def start_dispatcher(enabled_departments: list[dict]) -> AsyncIOScheduler:
    """Create and start the APScheduler with per-dept heartbeat jobs."""
    scheduler = AsyncIOScheduler()

    for dept in enabled_departments:
        dept_id = dept.get("dept_id", "unknown")
        hb = dept.get("heartbeat", {})
        schedule = hb.get("schedule", "")

        if not schedule:
            log.warning("Dept %s has heartbeat enabled but no schedule", dept_id)
            continue

        try:
            trigger = CronTrigger.from_crontab(schedule)
        except ValueError:
            log.error("Invalid cron schedule for %s: %s", dept_id, schedule)
            continue

        scheduler.add_job(
            _heartbeat_tick,
            trigger=trigger,
            kwargs={
                "dept_id": dept_id,
                "context_sources": hb.get("context_sources", []),
                "outbound_actions": hb.get("outbound_actions", []),
            },
            id=f"heartbeat_{dept_id}",
            replace_existing=True,
        )
        log.info("Scheduled heartbeat for %s: %s", dept_id, schedule)

    scheduler.start()
    return scheduler


async def _heartbeat_tick(dept_id: str, context_sources: list[str], outbound_actions: list[str]):
    """Single heartbeat tick for a department."""
    log.info("Heartbeat tick for %s", dept_id)

    # 1. Gather context from configured sources
    context = await gather_context(dept_id, context_sources)

    if "(no context available)" in context:
        log.info("No context for %s, skipping orchestrator invocation", dept_id)
        return

    # 2. Invoke department orchestrator in proactive mode
    result = await invoke_proactive(dept_id, context)

    if result is None:
        log.warning("Proactive invocation returned nothing for %s", dept_id)
        return

    # 3. Route outbound actions (all go through staging gate — no direct writes)
    action = result.get("action")
    if action and outbound_actions:
        log.info("Heartbeat %s produced action: %s (routing via staging)", dept_id, action)
        # Outbound actions route through existing staging pipeline
        # No new write paths — lethal trifecta unchanged
