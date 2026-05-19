"""API endpoint for cross-department query routing."""
import logging

from fastapi import APIRouter, HTTPException, Request

from .auth import AuthError, extract_claims
from .rate_limit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cross-dept", tags=["cross-department"])


@router.post("/query")
@limiter.limit("20/minute")
async def cross_dept_query(request: Request):
    """Route a query across multiple departments and synthesize results."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    body = await request.json()
    query = body.get("query", "")
    if not query:
        raise HTTPException(400, "query field required")

    try:
        from services.shared.cross_dept_router import detect_departments, route_cross_dept

        departments = body.get("departments")
        if not departments:
            departments = detect_departments(query)

        result = await route_cross_dept(
            query=query,
            departments=departments,
            user_id=claims.sub,
        )

        return result
    except ImportError:
        raise HTTPException(501, "Cross-department router not available")


@router.post("/detect")
@limiter.limit("30/minute")
async def detect_dept(request: Request):
    """Detect which departments a query is relevant to (without executing)."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    body = await request.json()
    query = body.get("query", "")

    try:
        from services.shared.cross_dept_router import detect_departments
        departments = detect_departments(query)
        return {"query": query, "departments": departments}
    except ImportError:
        raise HTTPException(501, "Cross-department router not available")
