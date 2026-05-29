"""Escalation list endpoint with department-scoped RBAC.

Provides a read-only view of escalations filtered by the caller's
department as derived from their JWT claims.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.gateway.src.auth import check_dept_access, extract_claims
from services.gateway.src.utils import SEVERITY_ORDER_SQL, serialize_row

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/escalations", tags=["escalations"])

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_escalations(
    request: Request,
    dept: str | None = None,
) -> JSONResponse:
    """List escalations scoped to a department.

    Returns escalations ordered by severity ASC, created_at DESC so the
    most critical and most recent appear first. Caller may pass `?dept=`
    to target a non-default department; access is verified.
    """
    claims = extract_claims(request)
    target_dept = (dept or claims.dept).lower()
    if dept and dept.lower() != (claims.dept or "").lower():
        check_dept_access(claims, target_dept, request=request)

    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM escalations WHERE dept = $1 "
            f"ORDER BY {SEVERITY_ORDER_SQL}, created_at DESC",
            target_dept,
        )

    escalations = [serialize_row(dict(r)) for r in rows]

    logger.info(
        "escalations_listed",
        dept=target_dept,
        count=len(escalations),
    )

    return JSONResponse(content={"escalations": escalations, "total": len(escalations)})
