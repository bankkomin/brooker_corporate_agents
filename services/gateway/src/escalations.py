"""Escalation list endpoint with department-scoped RBAC.

Provides a read-only view of escalations filtered by the caller's
department as derived from their JWT claims.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.gateway.src.auth import extract_claims
from services.gateway.src.utils import serialize_row

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/escalations", tags=["escalations"])

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_escalations(request: Request) -> JSONResponse:
    """List escalations scoped to the caller's department.

    Returns escalations ordered by severity ASC, created_at DESC so the
    most critical and most recent appear first.
    """
    claims = extract_claims(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM escalations WHERE dept = $1 "
            "ORDER BY severity ASC, created_at DESC",
            claims.dept,
        )

    escalations = [serialize_row(dict(r)) for r in rows]

    logger.info(
        "escalations_listed",
        dept=claims.dept,
        count=len(escalations),
    )

    return JSONResponse(content={"escalations": escalations, "total": len(escalations)})
