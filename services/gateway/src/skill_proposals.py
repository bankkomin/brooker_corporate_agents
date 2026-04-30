"""API endpoints for skill proposal review."""
import logging

from fastapi import APIRouter, HTTPException, Request

from .auth import AuthError, extract_claims
from .rate_limit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skill-proposals", tags=["skill-proposals"])


@router.get("")
@limiter.limit("30/minute")
async def list_proposals(request: Request, status: str = "hod_review"):
    """List skill proposals filtered by status. Requires authentication."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    db = request.app.state.db_pool
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, dept_id, agent_id, skill_path, trigger, evidence,
                      status, proposed_diff, created_at
               FROM agent_skill_proposals
               WHERE status = $1
               ORDER BY created_at DESC""",
            status,
        )
    return {
        "proposals": [
            {
                "id": r["id"],
                "dept_id": r["dept_id"],
                "agent_id": r["agent_id"],
                "skill_path": r["skill_path"],
                "trigger": r["trigger"],
                "evidence": r["evidence"],
                "status": r["status"],
                "proposed_diff": r["proposed_diff"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


@router.post("/{proposal_id}/decision")
@limiter.limit("10/minute")
async def decide_proposal(proposal_id: int, request: Request):
    """Approve or reject a skill proposal. Requires 'approve' permission."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if "approve" not in claims.permissions and claims.role not in ("admin", "ceo", "hod"):
        raise HTTPException(status_code=403, detail="Approve permission required")

    body = await request.json()
    action = body.get("action")
    if action not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="action must be 'approved' or 'rejected'")

    db = request.app.state.db_pool
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, dept_id FROM agent_skill_proposals WHERE id = $1", proposal_id
        )
        if row is None:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

        await conn.execute(
            """UPDATE agent_skill_proposals
               SET status = $2, hod_decision_at = NOW()
               WHERE id = $1""",
            proposal_id, action,
        )

    log.info("Skill proposal %d: %s by %s", proposal_id, action, claims.sub)
    return {"id": proposal_id, "status": action, "decided_by": claims.sub}
