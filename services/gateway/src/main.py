"""Gateway service — API entrypoint for the Corporate AI Agent system."""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request

from services.gateway.src.analytics import router as analytics_router
from services.gateway.src.auth import AuthError, validate_jwt
from services.gateway.src.errors import auth_error_handler
from services.gateway.src.escalations import router as escalations_router
from services.gateway.src.proposals import router as proposals_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the asyncpg connection pool lifecycle."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        import asyncpg

        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        application.state.db_pool = pool
        logger.info("db_pool_created", dsn=database_url[:30] + "...")
    else:
        logger.warning("db_pool_skipped", reason="DATABASE_URL not set")

    yield

    pool = getattr(application.state, "db_pool", None)
    if pool is not None:
        await pool.close()
        logger.info("db_pool_closed")


app = FastAPI(
    title="Corporate AI Agents Gateway",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_exception_handler(AuthError, auth_error_handler)  # type: ignore[arg-type]
app.include_router(proposals_router)
app.include_router(escalations_router)
app.include_router(analytics_router)


@app.get("/")
async def root() -> dict:
    """Service information."""
    return {
        "name": "Corporate AI Agents Gateway",
        "version": "0.1.0",
        "environment": os.getenv("ENV", "development"),
    }


@app.post("/api/auth/validate")
async def validate_token_endpoint(request: Request) -> dict:
    """Validate a JWT and return claims. Used by approval-ui for server-side validation."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise AuthError("TOKEN_INVALID", "No token provided", 401)
    claims = validate_jwt(token)
    return {
        "valid": True,
        "dept": claims.dept,
        "role": claims.role,
        "sub": claims.sub,
        "permissions": list(claims.permissions),
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "gateway",
        "timestamp": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
