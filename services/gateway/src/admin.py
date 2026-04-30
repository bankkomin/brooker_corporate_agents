"""Admin API endpoints for knowledge gaps and system health."""
import logging

from fastapi import APIRouter, HTTPException, Request

from .auth import AuthError, extract_claims
from .rate_limit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

_ADMIN_ROLES = {"admin", "ceo", "cto", "hod"}


@router.get("/knowledge-gaps")
@limiter.limit("30/minute")
async def list_knowledge_gaps(request: Request):
    """List all knowledge gaps. Requires admin role."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if claims.role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")

    db = request.app.state.db_pool
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, dept_id, agent_id, query, hit_count,
                      llm_self_report, expected_doc_type, created_at, resolved_at
               FROM agent_knowledge_gaps
               ORDER BY created_at DESC
               LIMIT 500"""
        )
    return {
        "gaps": [
            {
                "id": r["id"],
                "dept_id": r["dept_id"],
                "agent_id": r["agent_id"],
                "query": r["query"],
                "hit_count": r["hit_count"],
                "llm_self_report": r["llm_self_report"],
                "expected_doc_type": r["expected_doc_type"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
            }
            for r in rows
        ]
    }


@router.post("/knowledge-gaps/{gap_id}/resolve")
@limiter.limit("10/minute")
async def resolve_gap(gap_id: int, request: Request):
    """Mark a knowledge gap as resolved. Requires admin role."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if claims.role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")

    db = request.app.state.db_pool
    async with db.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM agent_knowledge_gaps WHERE id = $1", gap_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Knowledge gap {gap_id} not found")

        await conn.execute(
            "UPDATE agent_knowledge_gaps SET resolved_at = NOW(), resolved_by = $2 WHERE id = $1",
            gap_id, claims.sub,
        )

    log.info("Knowledge gap %d resolved by %s", gap_id, claims.sub)
    return {"id": gap_id, "status": "resolved", "resolved_by": claims.sub}
