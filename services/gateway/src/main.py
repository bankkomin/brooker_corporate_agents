"""Gateway service — API entrypoint for the Corporate AI Agent system."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from services.gateway.src.analytics import router as analytics_router
from services.gateway.src.chat import router as chat_router
from services.gateway.src.auth import (
    AuthError,
    extract_claims,
    resolve_agent_permissions,
    permissions_from_access,
    validate_jwt,
)
from services.gateway.src.errors import auth_error_handler
from services.gateway.src.escalations import router as escalations_router
from services.gateway.src.proposals import router as proposals_router
from services.gateway.src.uploads import router as uploads_router

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4000", "http://localhost:5111"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AuthError, auth_error_handler)  # type: ignore[arg-type]


@app.middleware("http")
async def brooker_token_middleware(request: Request, call_next):
    """For Brooker-issued JWTs, resolve agent_access permissions before routing.

    Skips non-protected paths (/health, /docs, /).  For Brooker tokens,
    looks up the employee in agent_access and stores resolved permissions
    in request.state so downstream handlers can check them.
    """
    # Skip preflight and non-protected paths
    if request.method == "OPTIONS":
        return await call_next(request)
    skip_paths = {"/", "/health", "/docs", "/openapi.json"}
    if request.url.path in skip_paths:
        return await call_next(request)

    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        return await call_next(request)

    try:
        claims = validate_jwt(token)
    except AuthError:
        # Let the endpoint's own extract_claims() handle the error
        return await call_next(request)

    if claims.source == "brooker":
        pool = getattr(request.app.state, "db_pool", None)
        try:
            # Resolve by email (since employee_id in agent_access may be placeholder)
            access = await resolve_agent_permissions(
                pool, employee_id=None, email=claims.email, department_name="cac",
            )
            request.state.agent_permissions = permissions_from_access(access)
            request.state.brooker_email = claims.email
            request.state.brooker_employee_id = claims.sub
        except AuthError as exc:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.message, "code": exc.code},
            )

    return await call_next(request)


app.include_router(chat_router)
app.include_router(proposals_router)
app.include_router(escalations_router)
app.include_router(analytics_router)
app.include_router(uploads_router)


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
    """Validate a JWT and return claims. Accepts both CAC and Brooker tokens."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise AuthError("TOKEN_INVALID", "No token provided", 401)
    claims = validate_jwt(token)

    permissions = list(claims.permissions)
    if claims.source == "brooker":
        # Return agent_access permissions resolved by the middleware
        permissions = getattr(request.state, "agent_permissions", [])

    return {
        "valid": True,
        "dept": claims.dept,
        "role": claims.role,
        "sub": claims.sub,
        "email": claims.email,
        "source": claims.source,
        "permissions": permissions,
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
