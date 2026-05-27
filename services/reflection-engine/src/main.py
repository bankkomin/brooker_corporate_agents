from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI

from .config import settings
from .scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(settings.POSTGRES_DSN, min_size=2, max_size=5)
    scheduler = start_scheduler(app.state.db_pool)
    yield
    scheduler.shutdown(wait=False)
    await app.state.db_pool.close()


app = FastAPI(title="reflection-engine", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reflection-engine", "port": settings.PORT}


@app.post("/reflect/{dept_id}")
async def trigger_reflection(dept_id: str, dry_run: bool = False):
    """Manually trigger reflection for a department."""
    from .engine import run_dept_reflection
    result = await run_dept_reflection(dept_id, app.state.db_pool, dry_run=dry_run)
    return result


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
