from contextlib import asynccontextmanager

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
