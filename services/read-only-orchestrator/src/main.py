"""Consolidated read-only orchestrator — serves all read-only departments from one service."""
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI, HTTPException
from prometheus_client import make_asgi_app

from .config import settings
from .pipeline import run_query

log = logging.getLogger(__name__)


def _load_readonly_depts() -> dict:
    """Load read-only departments from config."""
    path = Path(settings.DEPARTMENTS_CONFIG)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    depts = data.get("departments", {})
    if isinstance(depts, dict):
        return {k: v for k, v in depts.items()
                if v.get("capabilityTier") == "read_only" and v.get("live", False)}
    return {d["dept_id"]: d for d in depts
            if d.get("capabilityTier") == "read_only" and d.get("live", False)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(settings.POSTGRES_DSN, min_size=2, max_size=10)
    app.state.readonly_depts = _load_readonly_depts()
    log.info("Serving %d read-only departments: %s",
             len(app.state.readonly_depts), list(app.state.readonly_depts.keys()))
    yield
    await app.state.db_pool.close()


app = FastAPI(title="read-only-orchestrator", version="0.1.0", lifespan=lifespan)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "read-only-orchestrator",
        "port": settings.PORT,
        "departments": list(app.state.readonly_depts.keys()),
    }


@app.post("/query/{dept_id}")
async def query(dept_id: str, request: dict):
    """Query endpoint for any read-only department."""
    if dept_id not in app.state.readonly_depts:
        raise HTTPException(404, f"Department '{dept_id}' not found or not read-only")

    dept_config = app.state.readonly_depts[dept_id]
    query_text = request.get("query", "")
    user_id = request.get("user_id", "unknown")

    if not query_text:
        raise HTTPException(400, "query field required")

    result = await run_query(
        query=query_text,
        dept_id=dept_id,
        dept_config=dept_config,
        user_id=user_id,
        db_pool=app.state.db_pool,
    )
    return result
