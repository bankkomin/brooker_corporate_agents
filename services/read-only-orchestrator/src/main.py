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
    """Load departments served by this multi-tenant orchestrator.

    Includes both read_only depts AND write depts that don't yet have their
    own orchestrator (finance/cio/vcc) — those get read-only access here
    until their real graph implementations land.
    """
    path = Path(settings.DEPARTMENTS_CONFIG)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    depts = data.get("departments", {})
    accepted_tiers = {"read_only", "write"}
    if isinstance(depts, dict):
        return {k: v for k, v in depts.items()
                if v.get("capabilityTier") in accepted_tiers and v.get("live", False)}
    return {d["dept_id"]: d for d in depts
            if d.get("capabilityTier") in accepted_tiers and d.get("live", False)}


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


async def _dispatch_query(dept_id: str, request: dict) -> dict:
    """Shared query dispatcher used by both /query and /query/{dept_id}."""
    if dept_id not in app.state.readonly_depts:
        raise HTTPException(404, f"Department '{dept_id}' not found or not read-only")

    dept_config = app.state.readonly_depts[dept_id]
    query_text = request.get("query", "")
    user_id = request.get("user_id", "unknown")

    if not query_text:
        raise HTTPException(400, "query field required")

    return await run_query(
        query=query_text,
        dept_id=dept_id,
        dept_config=dept_config,
        user_id=user_id,
        db_pool=app.state.db_pool,
    )


@app.post("/query")
async def query_body(request: dict):
    """Uniform query endpoint — gateway sends dept_id in the body.

    Matches the shape used by cac-orchestrator and hr-orchestrator so the
    gateway can call every orchestrator the same way.
    """
    dept_id = request.get("dept_id")
    if not dept_id:
        raise HTTPException(400, "dept_id field required")
    return await _dispatch_query(dept_id, request)


@app.post("/query/{dept_id}")
async def query(dept_id: str, request: dict):
    """Legacy path-based query endpoint, retained for direct callers."""
    return await _dispatch_query(dept_id, request)
