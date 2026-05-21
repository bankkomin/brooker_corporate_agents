"""Sync-back service — FastAPI app.

Endpoints:
  GET  /health             — liveness probe
  POST /process-approved   — copy approved proposal manifests to staging/approved/
  POST /archive-completed  — move synced/rejected proposals to archive
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
