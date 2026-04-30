from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await asyncpg.create_pool(settings.POSTGRES_DSN, min_size=2, max_size=5)
    yield
    await app.state.db_pool.close()


app = FastAPI(title=f"{settings.DEPT_ID}-orchestrator", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": f"{settings.DEPT_ID}-orchestrator", "port": settings.PORT}


@app.post("/query")
async def query(request: dict):
    """Main query endpoint — routes through LangGraph pipeline."""
    # TODO: Wire LangGraph graph for {DEPT_NAME} department
    return {"error": "not implemented — fill in per-dept stage"}


@app.post("/proactive")
async def proactive(request: dict):
    """Heartbeat proactive endpoint — invoked by heartbeat service."""
    # TODO: Implement proactive mode for {DEPT_NAME}
    return {"action": None, "message": "proactive mode not yet configured"}
