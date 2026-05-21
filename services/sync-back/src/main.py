"""Sync-back service — FastAPI app.

Endpoints:
  GET  /health             — liveness probe
  POST /sync               — full cycle: apply approved Excel writes then archive
  POST /process-approved   — apply approved manifests (write Excel, mark synced)
  POST /archive-completed  — move synced/rejected proposals to archive

Data zone contract (enforced here and in openpyxl_writer):
  READS  from: /data/mirror/   (Zone 1 — read-only replica)
  WRITES to:   /data/staging/  (Zone 2 — staging copies of modified Excel)
               /data/archive/  (Zone 4 — permanent audit trail + final workbook)
  NEVER writes to /data/mirror/.
"""
from dotenv import load_dotenv
load_dotenv()

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
import structlog
from fastapi import FastAPI, HTTPException

from .archiver import archive_completed
from .config import DATABASE_URL
from .processor import process_approved

logger = structlog.get_logger(__name__)

_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _pool
    logger.info("sync_back.startup", database_url=DATABASE_URL.split("@")[-1])
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    logger.info("sync_back.pool_ready")
    yield
    if _pool:
        await _pool.close()
    logger.info("sync_back.shutdown")


app = FastAPI(
    title="sync-back",
    description="Copies approved proposals to staging and archives completed ones.",
    version="0.1.0",
    lifespan=lifespan,
)


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise HTTPException(status_code=503, detail="Database pool not ready")
    return _pool


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 when the service is running."""
    return {"status": "ok", "service": "sync-back"}


@app.post("/process-approved")
async def process_approved_endpoint() -> dict[str, int]:
    """Copy manifests for all newly approved proposals to staging/approved/.

    Idempotent — already-written manifests are not re-written.
    Returns the number of proposals processed in this call.
    """
    pool = _get_pool()
    try:
        count = await process_approved(pool)
    except Exception as exc:
        logger.error("process_approved.error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"processed": count}


@app.post("/archive-completed")
async def archive_completed_endpoint() -> dict[str, int]:
    """Move synced/rejected proposals to the archive directory.

    Idempotent — already-archived proposals are skipped.
    Returns the number of proposals archived in this call.
    """
    pool = _get_pool()
    try:
        count = await archive_completed(pool)
    except Exception as exc:
        logger.error("archive_completed.error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"archived": count}


@app.post("/sync")
async def sync_endpoint() -> dict[str, int]:
    """Full sync cycle: apply approved Excel writes then archive completed proposals.

    Idempotent — safe to call repeatedly (e.g. from a cron/watchdog).

    Flow:
      1. Scan DB for approved proposals with no synced_at.
      2. For each: read source Excel from /data/mirror/ (read-only),
         write new_value to a staging copy in /data/staging/approved/{id}/,
         mark DB row as 'synced'.
      3. Archive all synced/rejected proposals to /data/archive/YYYY/MM/{id}/.
         The archive copy of the modified workbook is the durable output —
         real corporate sync (Zone 0) is a separate external step performed
         by the sync-mirror service.

    Returns counts for both phases.
    """
    pool = _get_pool()
    try:
        processed = await process_approved(pool)
    except Exception as exc:
        logger.error("sync.process_approved.error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"process_approved failed: {exc}") from exc

    try:
        archived = await archive_completed(pool)
    except Exception as exc:
        logger.error("sync.archive_completed.error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"archive_completed failed: {exc}") from exc

    logger.info("sync.done", processed=processed, archived=archived)
    return {"processed": processed, "archived": archived}
