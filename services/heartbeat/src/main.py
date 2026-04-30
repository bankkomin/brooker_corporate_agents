import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .config_reader import load_enabled_departments
from .dispatcher import start_dispatcher

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    enabled = load_enabled_departments(settings.CONFIG_PATH)
    if enabled:
        log.info("Heartbeat enabled for %d departments: %s", len(enabled), [d["dept_id"] for d in enabled])
        scheduler = start_dispatcher(enabled)
        yield
        scheduler.shutdown(wait=False)
    else:
        log.info("Heartbeat: no departments enabled, running idle")
        yield


app = FastAPI(title="heartbeat", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    enabled = load_enabled_departments(settings.CONFIG_PATH)
    return {
        "status": "ok",
        "service": "heartbeat",
        "port": settings.PORT,
        "enabled_departments": [d["dept_id"] for d in enabled],
    }


@app.get("/status")
async def status():
    """Show which departments have heartbeat enabled and their schedules."""
    enabled = load_enabled_departments(settings.CONFIG_PATH)
    return {
        "departments": [
            {
                "dept_id": d["dept_id"],
                "schedule": d.get("heartbeat", {}).get("schedule", ""),
                "context_sources": d.get("heartbeat", {}).get("context_sources", []),
                "outbound_actions": d.get("heartbeat", {}).get("outbound_actions", []),
            }
            for d in enabled
        ]
    }
