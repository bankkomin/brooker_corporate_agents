"""Department orchestrator scaffold.

How to use this template:

1. Copy `services/_template-orchestrator/` to `services/<dept>-orchestrator/`.
2. Update settings in `config.py` (DEPT_ID, DEPT_NAME, AGENT_ID, PORT).
3. Add specialists under `agents/` mirroring the pattern in
   `services/cac-orchestrator/src/agents/`.
4. Implement a real `graph.py` (copy from cac-orchestrator for write-capable
   depts or from hr-orchestrator for read-only depts).
5. Add a service entry to `docker-compose.yml`.
6. Add `<DEPT>_ORCHESTRATOR_URL=http://<dept>-orchestrator:<PORT>` to the
   gateway's env.
7. Flip the dept's `live: true` in `config/departments.json`.

This scaffold returns 501 from /query until the graph is wired so that an
accidentally-deployed copy fails loudly rather than appearing healthy.
"""
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(
        settings.POSTGRES_DSN, min_size=2, max_size=5,
    )
    yield
    await app.state.db_pool.close()


app = FastAPI(
    title=f"{settings.DEPT_ID}-orchestrator",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.AGENT_ID,
        "dept_id": settings.DEPT_ID,
        "port": settings.PORT,
        "write_capable": settings.WRITE_CAPABLE,
    }


@app.post("/query")
async def query(request: dict):
    """LangGraph entry point — wire this in your dept implementation.

    Expected request body (matches cac-orchestrator/hr-orchestrator):
        query: str
        user_id: str
        channel: str
        thread_ts: str | None
        dept_id: str | None     # gateway forwards the resolved slug
        files: list[dict]       # portal-attached files (optional)
        auth_token: str | None  # passthrough for portal file fetches
        portal_base_url: str | None
    """
    return {
        "error": "Orchestrator not implemented",
        "code": "ORCHESTRATOR_TEMPLATE",
        "dept_id": settings.DEPT_ID,
        "hint": "Wire LangGraph in graph.py — see services/cac-orchestrator/src/graph.py",
    }


@app.post("/proactive")
async def proactive(request: dict):
    """Heartbeat proactive endpoint — invoked by the heartbeat service.

    Optional: only implement if the dept's `heartbeat.enabled` is true in
    `config/departments.json`.
    """
    return {
        "action": None,
        "message": "Proactive mode not yet configured for this orchestrator",
    }
