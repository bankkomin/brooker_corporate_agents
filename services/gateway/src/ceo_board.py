"""CEO board — cross-department read-only aggregator.

Returns proposals (pending, plus approved/rejected decided in the last 14 days)
and open escalations across ALL departments, shaped as kanban columns.

Auth: caller's role must have globalAccess.roles[role].canRead containing "*"
(currently only "ceo" satisfies this). For Brooker-sourced tokens, the
brooker_token_middleware short-circuits the per-dept agent_access lookup for
roles with wildcard read — see note in main.brooker_token_middleware.

Note (carry-over from code review #6, deferred): wildcard-read authorisation
trusts the JWT `role` claim. Tightening this against agent_access for Brooker
tokens requires schema work (provisioning cross-dept agent_access rows for
executives) and is tracked separately.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.gateway.src.auth import AuthError, extract_claims, role_can_read_all
from services.gateway.src.rate_limit import limiter
from services.gateway.src.utils import SEVERITY_ORDER_SQL, serialize_row

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/ceo", tags=["ceo"])

# Window for the "approved/rejected" columns. Filtered against
# approval_decisions.decided_at — NOT staging_proposals.created_at —
# so a proposal created long ago but decided yesterday still appears.
_RESOLVED_WINDOW_DAYS = 14

# Hard cap per column. Prevents an unbounded backlog from rendering the page
# unusable or saturating the asyncpg pool. UI surfaces a `truncated` flag.
_COLUMN_LIMIT = 200


def _require_wildcard_read(claims) -> None:
    """Raise 403 unless the caller's role has canRead containing '*'."""
    if role_can_read_all(claims.role):
        return
    raise AuthError(
        "CEO_BOARD_FORBIDDEN",
        f"Role '{claims.role}' is not permitted to view the CEO board",
        status_code=403,
    )


@router.get("/board")
@limiter.limit("30/minute")
async def get_ceo_board(request: Request) -> JSONResponse:
    """Aggregate proposals + escalations across all departments into columns."""
    claims = extract_claims(request)
    _require_wildcard_read(claims)

    pool = request.app.state.db_pool

    pending_sql = (
        "SELECT * FROM staging_proposals "
        "WHERE status = 'pending' "
        "ORDER BY created_at DESC "
        f"LIMIT {_COLUMN_LIMIT + 1}"
    )

    # Approved / rejected: join approval_decisions so the window filters on
    # the DECISION time, not the proposal creation time. Includes 'edited'
    # decisions which also transition the proposal to status='approved'.
    approved_sql = (
        "SELECT sp.*, ad.decided_at AS decided_at "
        "FROM staging_proposals sp "
        "JOIN approval_decisions ad ON ad.proposal_id = sp.id "
        "WHERE sp.status = 'approved' "
        "  AND ad.decision IN ('approved', 'edited') "
        "  AND ad.decided_at > NOW() - ($1::int * INTERVAL '1 day') "
        "ORDER BY ad.decided_at DESC "
        f"LIMIT {_COLUMN_LIMIT + 1}"
    )

    rejected_sql = (
        "SELECT sp.*, ad.decided_at AS decided_at "
        "FROM staging_proposals sp "
        "JOIN approval_decisions ad ON ad.proposal_id = sp.id "
        "WHERE sp.status = 'rejected' "
        "  AND ad.decision = 'rejected' "
        "  AND ad.decided_at > NOW() - ($1::int * INTERVAL '1 day') "
        "ORDER BY ad.decided_at DESC "
        f"LIMIT {_COLUMN_LIMIT + 1}"
    )

    escalations_sql = (
        "SELECT * FROM escalations WHERE resolved_at IS NULL "
        f"ORDER BY {SEVERITY_ORDER_SQL}, created_at DESC "
        f"LIMIT {_COLUMN_LIMIT + 1}"
    )

    async with pool.acquire() as conn:
        pending = await conn.fetch(pending_sql)
        approved = await conn.fetch(approved_sql, _RESOLVED_WINDOW_DAYS)
        rejected = await conn.fetch(rejected_sql, _RESOLVED_WINDOW_DAYS)
        escalations = await conn.fetch(escalations_sql)

    def _bucket(rows: list) -> tuple[list[dict], bool]:
        truncated = len(rows) > _COLUMN_LIMIT
        kept = rows[:_COLUMN_LIMIT]
        return [serialize_row(dict(r)) for r in kept], truncated

    pending_rows, pending_trunc = _bucket(pending)
    approved_rows, approved_trunc = _bucket(approved)
    rejected_rows, rejected_trunc = _bucket(rejected)
    escalated_rows, escalated_trunc = _bucket(escalations)

    payload = {
        "columns": {
            "escalated": escalated_rows,
            "pending": pending_rows,
            "approved": approved_rows,
            "rejected": rejected_rows,
        },
        "totals": {
            "escalated": len(escalated_rows),
            "pending": len(pending_rows),
            "approved": len(approved_rows),
            "rejected": len(rejected_rows),
        },
        "truncated": {
            "escalated": escalated_trunc,
            "pending": pending_trunc,
            "approved": approved_trunc,
            "rejected": rejected_trunc,
        },
        "window_days": _RESOLVED_WINDOW_DAYS,
    }

    # Audit event — cross-dept read of restricted data. Persistent audit table
    # tracked separately (review finding #9); for now structlog captures the
    # full payload shape so logs can answer "who saw what when".
    logger.info(
        "ceo_board_viewed",
        subject=claims.sub,
        role=claims.role,
        source=claims.source,
        email=getattr(claims, "email", None),
        client_ip=request.client.host if request.client else None,
        totals=payload["totals"],
        truncated=payload["truncated"],
    )

    return JSONResponse(content=payload)
