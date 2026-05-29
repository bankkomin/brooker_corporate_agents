"""Reflection Engine — FastAPI application entry point.

Endpoints:
  GET  /health              — liveness probe
  POST /reflect/{dept_id}   — trigger reflection for one department
  POST /reflect/all         — trigger reflection for all live departments

Nightly schedule:
  APScheduler cron job fires at REFLECTION_CRON_HOUR:REFLECTION_CRON_MINUTE (default 02:00 UTC).
  Alternatively, run from cron/k8s CronJob via:
    curl -X POST http://reflection-engine:3008/reflect/all

CRITICAL: this service NEVER writes to /data/mirror/.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .config import settings
from .scheduler import start_scheduler

# ── Structlog configuration ───────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
logging.basicConfig(level=logging.INFO)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start DB pool and APScheduler; shut down cleanly on exit.

    If Postgres is unavailable at startup the service still starts —
    individual /reflect calls will degrade gracefully.
    """
    db_pool: asyncpg.Pool | None = None
    try:
        db_pool = await asyncpg.create_pool(settings.POSTGRES_DSN, min_size=2, max_size=5)
        log.info("db_pool_created")
    except Exception:
        log.warning("db_pool_unavailable_starting_without_db", exc_info=True)

    app.state.db_pool = db_pool
    scheduler = start_scheduler(db_pool)

    yield

    scheduler.shutdown(wait=False)
    if db_pool:
        await db_pool.close()
    log.info("reflection_engine_shutdown")


app = FastAPI(title="reflection-engine", version="0.2.0", lifespan=lifespan)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "reflection-engine",
        "port": settings.PORT,
        "db_available": app.state.db_pool is not None,
    }


@app.post("/reflect/{dept_id}")
async def trigger_reflection(dept_id: str, dry_run: bool = False) -> JSONResponse:
    """Manually trigger reflection for a single department.

    Query param ?dry_run=true skips LLM calls and file writes (safe for testing).
    """
    if app.state.db_pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")

    from .engine import run_dept_reflection

    result = await run_dept_reflection(dept_id, app.state.db_pool, dry_run=dry_run)
    status_code = 200 if "error" not in result else 500
    return JSONResponse(content=result, status_code=status_code)


@app.post("/reflect/all")
async def trigger_all_reflection(dry_run: bool = False) -> JSONResponse:
    """Trigger reflection for every live department listed in departments.json.

    Iterates the config and calls run_dept_reflection per department.
    Errors in individual departments are captured per-result, not surfaced as 500.
    """
    if app.state.db_pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")

    config_path = Path("/app/config/departments.json")
    if not config_path.exists():
        raise HTTPException(status_code=503, detail="departments.json not found")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    departments = data.get("departments", [])
    if isinstance(departments, dict):
        dept_list = [{"dept_id": k, **v} for k, v in departments.items()]
    else:
        dept_list = departments

    from .engine import run_dept_reflection

    results: list[dict] = []
    for dept in dept_list:
        if not dept.get("live", False):
            continue
        dept_id: str = str(dept.get("dept_id", dept.get("shortName", "unknown")))
        try:
            result = await run_dept_reflection(dept_id, app.state.db_pool, dry_run=dry_run)
        except Exception:
            log.exception("reflect_all_dept_error", dept=dept_id)
            result = {"dept_id": dept_id, "error": "unhandled exception — see logs"}
        results.append(result)

    return JSONResponse(content={"departments_processed": len(results), "results": results})


@app.post("/synthesis-scan")
async def trigger_synthesis_scan_endpoint():
    """Manually fire the same POST that the nightly synthesis-scan cron does.

    Returns the rag-ingestion response (candidates / proposed / proposal_ids)
    or a failure payload if the call could not complete.
    """
    from .synthesis_scan_trigger import trigger_synthesis_scan
    return await trigger_synthesis_scan(
        rag_ingestion_url=settings.RAG_INGESTION_URL,
        timeout_seconds=settings.SYNTHESIS_SCAN_TIMEOUT,
    )


@app.post("/vault-health-check")
async def trigger_vault_health_check():
    """Manually trigger the vault-wide health check (also runs nightly per scheduler)."""
    from .vault_health_check import run_and_persist
    report = await run_and_persist(Path(settings.VAULT_ROOT))
    return {
        "status": "ok",
        "run_date": report.run_date.isoformat(),
        "critical": report.critical_count,
        "warning": report.warning_count,
        "info": report.info_count,
        "depts_scanned": report.depts_scanned,
        "notes_scanned": report.notes_scanned,
        "report_path": f"health-reports/{report.run_date.isoformat()}.md",
    }
