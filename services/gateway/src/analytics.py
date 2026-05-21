"""Analytics summary endpoint with department-scoped RBAC.

Provides a dashboard summary of proposals and escalations for the
caller's department, derived from their JWT claims.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.gateway.src.auth import check_dept_access, extract_claims

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/summary")
async def analytics_summary(
    request: Request,
    dept: str | None = None,
) -> JSONResponse:
    """Return a summary of proposals and escalations for a department.

    Scoping precedence: `?dept=` query param (with access check) wins;
    otherwise falls back to the caller's JWT dept.

    Executes 4 queries:
        - pending_count: proposals with status='pending'
        - approved_today: proposals approved on the current calendar day
        - active_escalations: escalations with resolved_at IS NULL
        - avg_confidence: average confidence across all proposals
    """
    claims = extract_claims(request)
    target_dept = (dept or claims.dept).lower()
    if dept and dept.lower() != (claims.dept or "").lower():
        check_dept_access(claims, target_dept, request=request)

    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        pending_count: int = await conn.fetchval(
            "SELECT COUNT(*) FROM staging_proposals "
            "WHERE dept = $1 AND status = 'pending'",
            target_dept,
        )

        approved_today: int = await conn.fetchval(
            "SELECT COUNT(*) FROM staging_proposals "
            "WHERE dept = $1 AND status = 'approved' "
            "AND created_at >= CURRENT_DATE",
            target_dept,
        )

        active_escalations: int = await conn.fetchval(
            "SELECT COUNT(*) FROM escalations "
            "WHERE dept = $1 AND resolved_at IS NULL",
            target_dept,
        )

        avg_confidence: float | None = await conn.fetchval(
            "SELECT AVG(confidence) FROM staging_proposals WHERE dept = $1",
            target_dept,
        )

    # Convert Decimal/None to Python float or None for JSON serialisation
    avg_conf_out = float(avg_confidence) if avg_confidence is not None else None

    logger.info(
        "analytics_summary_fetched",
        dept=target_dept,
        pending=pending_count,
        approved_today=approved_today,
        escalations=active_escalations,
    )

    return JSONResponse(
        content={
            "pending": int(pending_count),
            "approved_today": int(approved_today),
            "escalations": int(active_escalations),
            "avg_confidence": avg_conf_out,
        }
    )
