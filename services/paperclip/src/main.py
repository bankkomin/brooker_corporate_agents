"""Paperclip service — audit and orchestration hub."""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.auth import verify_api_key
from src.db.connection import close_pool, get_pool
from src.routes import departments, heartbeat, tickets, webhooks

logger = structlog.get_logger()


class AuthMiddleware(BaseHTTPMiddleware):
    """API key authentication middleware."""

    async def dispatch(self, request, call_next):
        try:
            await verify_api_key(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown resources."""
    logger.info("paperclip_starting")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SELECT 1")
    logger.info("paperclip_db_connected")
    yield
    await close_pool()
    logger.info("paperclip_stopped")


app = FastAPI(
    title="Paperclip",
    version="0.1.0",
    description="Audit and orchestration hub for CAC agent system",
    lifespan=lifespan,
)

app.add_middleware(AuthMiddleware)

app.include_router(tickets.router)
app.include_router(heartbeat.router)
app.include_router(departments.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    """Health check endpoint for Docker."""
    return {"status": "healthy", "service": "paperclip"}
