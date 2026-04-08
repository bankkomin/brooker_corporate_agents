"""Proposal CRUD endpoints with department-scoped RBAC.

Provides list, detail, approve, reject, and edit endpoints for staging proposals.
Every query enforces department scoping via JWT claims.
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.gateway.src.auth import check_dept_access, extract_claims
from services.gateway.src.errors import ErrorResponse
from services.gateway.src.hooks import on_proposal_approved, on_proposal_rejected
from services.gateway.src.utils import serialize_row

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/proposals", tags=["proposals"])

# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------


class RejectBody(BaseModel):
    """Body for the reject endpoint."""

    reason: str | None = None


class EditBody(BaseModel):
    """Body for the edit endpoint."""

    edited_value: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_proposal(proposal_id: str, pool: Any) -> dict[str, Any] | None:
    """Fetch a single proposal by ID (no dept filter — caller checks access)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM staging_proposals WHERE id = $1",
            proposal_id,
        )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_proposals(
    request: Request,
    status: str | None = None,
) -> JSONResponse:
    """List proposals scoped to the caller's department.

    Query params:
        status: Optional filter by proposal status (pending/approved/rejected).
    """
    claims = extract_claims(request)
    pool = request.app.state.db_pool

    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM staging_proposals WHERE dept = $1 AND status = $2 "
                "ORDER BY created_at DESC",
                claims.dept,
                status,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM staging_proposals WHERE dept = $1 "
                "ORDER BY created_at DESC",
                claims.dept,
            )

    proposals = [serialize_row(dict(r)) for r in rows]
    return JSONResponse(content={"proposals": proposals, "total": len(proposals)})


@router.get("/{proposal_id}")
async def get_proposal(request: Request, proposal_id: str) -> JSONResponse:
    """Get a single proposal by ID with dept access check."""
    claims = extract_claims(request)
    pool = request.app.state.db_pool
    proposal = await _fetch_proposal(proposal_id, pool)

    if proposal is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="Proposal not found",
                code="PROPOSAL_NOT_FOUND",
            ).model_dump(),
        )

    # RBAC: check dept access (raises AuthError → 403 if mismatch)
    check_dept_access(claims, proposal["dept"])

    return JSONResponse(content=serialize_row(proposal))


@router.post("/{proposal_id}/approve")
async def approve_proposal(request: Request, proposal_id: str) -> JSONResponse:
    """Approve a pending proposal (atomic UPDATE to avoid TOCTOU race)."""
    claims = extract_claims(request)

    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        # Atomic: only transitions pending -> approved
        result = await conn.fetchrow(
            "UPDATE staging_proposals SET status = 'approved' "
            "WHERE id = $1 AND status = 'pending' RETURNING *",
            proposal_id,
        )
        if result is None:
            # Distinguish not-found vs wrong-dept vs already-decided
            existing = await conn.fetchrow(
                "SELECT id, status, dept FROM staging_proposals WHERE id = $1",
                proposal_id,
            )
            if existing is None:
                return JSONResponse(
                    status_code=404,
                    content=ErrorResponse(
                        error="Proposal not found",
                        code="PROPOSAL_NOT_FOUND",
                    ).model_dump(),
                )
            check_dept_access(claims, existing["dept"])
            return JSONResponse(
                status_code=409,
                content=ErrorResponse(
                    error=f"Proposal is already {existing['status']}",
                    code="PROPOSAL_NOT_PENDING",
                ).model_dump(),
            )

        check_dept_access(claims, result["dept"])

        await conn.execute(
            "INSERT INTO approval_decisions (proposal_id, decision, decided_by, dept) "
            "VALUES ($1, 'approved', $2, $3)",
            proposal_id,
            claims.sub,
            claims.dept,
        )

    logger.info(
        "proposal_decision",
        proposal_id=proposal_id,
        decision="approved",
        decided_by=claims.sub,
        dept=claims.dept,
    )

    # Fire-and-forget downstream triggers — never block the gateway response
    try:
        await on_proposal_approved(proposal_id, claims.dept)
    except Exception as exc:
        logger.error("hook.approve.failed", proposal_id=proposal_id, error=str(exc))

    return JSONResponse(content={"status": "approved", "proposal_id": proposal_id})


@router.post("/{proposal_id}/reject")
async def reject_proposal(request: Request, proposal_id: str) -> JSONResponse:
    """Reject a pending proposal (atomic UPDATE to avoid TOCTOU race)."""
    claims = extract_claims(request)

    # Parse body
    try:
        body_json = await request.json()
    except Exception:
        body_json = {}

    reason = body_json.get("reason") if body_json else None
    if not reason:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="Rejection reason is required",
                code="REJECTION_REASON_REQUIRED",
            ).model_dump(),
        )

    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        # Atomic: only transitions pending -> rejected
        result = await conn.fetchrow(
            "UPDATE staging_proposals SET status = 'rejected' "
            "WHERE id = $1 AND status = 'pending' RETURNING *",
            proposal_id,
        )
        if result is None:
            existing = await conn.fetchrow(
                "SELECT id, status, dept FROM staging_proposals WHERE id = $1",
                proposal_id,
            )
            if existing is None:
                return JSONResponse(
                    status_code=404,
                    content=ErrorResponse(
                        error="Proposal not found",
                        code="PROPOSAL_NOT_FOUND",
                    ).model_dump(),
                )
            check_dept_access(claims, existing["dept"])
            return JSONResponse(
                status_code=409,
                content=ErrorResponse(
                    error=f"Proposal is already {existing['status']}",
                    code="PROPOSAL_NOT_PENDING",
                ).model_dump(),
            )

        check_dept_access(claims, result["dept"])

        await conn.execute(
            "INSERT INTO approval_decisions "
            "(proposal_id, decision, decided_by, dept, rejection_reason) "
            "VALUES ($1, 'rejected', $2, $3, $4)",
            proposal_id,
            claims.sub,
            claims.dept,
            reason,
        )

    logger.info(
        "proposal_decision",
        proposal_id=proposal_id,
        decision="rejected",
        decided_by=claims.sub,
        dept=claims.dept,
    )

    try:
        await on_proposal_rejected(proposal_id, claims.dept, reason)
    except Exception as exc:
        logger.error("hook.reject.failed", proposal_id=proposal_id, error=str(exc))

    return JSONResponse(content={"status": "rejected", "proposal_id": proposal_id})


@router.post("/{proposal_id}/edit")
async def edit_proposal(request: Request, proposal_id: str) -> JSONResponse:
    """Edit a proposal value and approve it (atomic UPDATE to avoid TOCTOU race)."""
    claims = extract_claims(request)

    try:
        body_json = await request.json()
    except Exception:
        body_json = {}

    edited_value = body_json.get("edited_value") if body_json else None
    if not edited_value:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error="Edited value is required",
                code="EDITED_VALUE_REQUIRED",
            ).model_dump(),
        )

    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        # Atomic: transition pending -> approved AND persist edited new_value
        result = await conn.fetchrow(
            "UPDATE staging_proposals SET status = 'approved', new_value = $2 "
            "WHERE id = $1 AND status = 'pending' RETURNING *",
            proposal_id,
            edited_value,
        )
        if result is None:
            existing = await conn.fetchrow(
                "SELECT id, status, dept FROM staging_proposals WHERE id = $1",
                proposal_id,
            )
            if existing is None:
                return JSONResponse(
                    status_code=404,
                    content=ErrorResponse(
                        error="Proposal not found",
                        code="PROPOSAL_NOT_FOUND",
                    ).model_dump(),
                )
            check_dept_access(claims, existing["dept"])
            return JSONResponse(
                status_code=409,
                content=ErrorResponse(
                    error=f"Proposal is already {existing['status']}",
                    code="PROPOSAL_NOT_PENDING",
                ).model_dump(),
            )

        check_dept_access(claims, result["dept"])

        await conn.execute(
            "INSERT INTO approval_decisions "
            "(proposal_id, decision, decided_by, dept, edited_value) "
            "VALUES ($1, 'edited', $2, $3, $4)",
            proposal_id,
            claims.sub,
            claims.dept,
            edited_value,
        )

    logger.info(
        "proposal_decision",
        proposal_id=proposal_id,
        decision="edited",
        decided_by=claims.sub,
        dept=claims.dept,
    )

    try:
        await on_proposal_approved(proposal_id, claims.dept)
    except Exception as exc:
        logger.error("hook.edit.failed", proposal_id=proposal_id, error=str(exc))

    return JSONResponse(content={"status": "approved", "proposal_id": proposal_id})
