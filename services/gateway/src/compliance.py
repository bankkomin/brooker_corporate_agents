"""API endpoints for compliance and audit trail export."""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .auth import AuthError, extract_claims
from .rate_limit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/compliance", tags=["compliance"])

_ADMIN_ROLES = {"admin", "ceo", "cto", "hod", "compliance"}


@router.get("/audit-trail")
@limiter.limit("5/minute")
async def export_audit(
    request: Request,
    dept_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",
):
    """Export full audit trail. Requires admin/compliance role."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if claims.role not in _ADMIN_ROLES:
        raise HTTPException(403, "Compliance/admin role required")

    from services.shared.compliance_export import export_audit_trail

    result = await export_audit_trail(
        request.app.state.db_pool, dept_id, start_date, end_date, format,
    )

    if format == "csv":
        return PlainTextResponse(
            result,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_trail.csv"},
        )
    return PlainTextResponse(result, media_type="application/json")


@router.get("/summary/{dept_id}/{quarter}")
@limiter.limit("10/minute")
async def compliance_summary(dept_id: str, quarter: str, request: Request):
    """Generate quarterly compliance summary."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if claims.role not in _ADMIN_ROLES:
        raise HTTPException(403, "Compliance/admin role required")

    from services.shared.compliance_export import generate_compliance_summary

    return await generate_compliance_summary(request.app.state.db_pool, dept_id, quarter)
