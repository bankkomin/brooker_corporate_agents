"""API endpoints for structured report generation, email ingestion, NLQ, and auto-approve."""
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from .auth import AuthError, extract_claims
from .rate_limit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Fix 1 — report_generator endpoints
# ---------------------------------------------------------------------------

@router.get("/weekly-brief/{dept_id}")
@limiter.limit("10/minute")
async def get_weekly_brief(dept_id: str, request: Request):
    """Generate a weekly department brief."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    from services.shared.report_generator import generate_weekly_brief
    report = await generate_weekly_brief(dept_id, dept_id.upper(), request.app.state.db_pool)

    return {
        "report_type": report.report_type,
        "dept_id": report.dept_id,
        "title": report.title,
        "period": {"start": report.period_start, "end": report.period_end},
        "sections": [
            {"title": s.title, "content": s.content, "priority": s.priority, "data": s.data}
            for s in report.sections
        ],
        "generated_at": report.generated_at.isoformat(),
    }


@router.get("/meeting-prep/{dept_id}")
@limiter.limit("10/minute")
async def get_meeting_prep(dept_id: str, request: Request, meeting_date: str = None):
    """Generate a pre-meeting preparation document."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    from services.shared.report_generator import generate_meeting_prep

    if not meeting_date:
        meeting_date = datetime.utcnow().strftime("%Y-%m-%d")

    report = await generate_meeting_prep(dept_id, dept_id.upper(), meeting_date, request.app.state.db_pool)

    return {
        "report_type": report.report_type,
        "dept_id": report.dept_id,
        "title": report.title,
        "sections": [
            {"title": s.title, "content": s.content, "priority": s.priority}
            for s in report.sections
        ],
        "generated_at": report.generated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Fix 2 — email_ingestion endpoint
# ---------------------------------------------------------------------------

@router.post("/email-ingestion/run")
@limiter.limit("5/minute")
async def run_email_ingestion(request: Request):
    """Trigger email ingestion cycle for all departments."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    if claims.role not in ("admin", "ceo", "cto"):
        raise HTTPException(403, "Admin role required")

    try:
        import os

        from services.shared.email_ingestion import EmailIngestionPipeline
        from services.shared.ms_graph_client import GraphConfig, MSGraphClient

        config = GraphConfig(
            tenant_id=os.environ.get("MS_TENANT_ID", ""),
            client_id=os.environ.get("MS_CLIENT_ID", ""),
            client_secret=os.environ.get("MS_CLIENT_SECRET", ""),
        )

        if not config.tenant_id or not config.client_id:
            return {"status": "skipped", "reason": "MS Graph credentials not configured"}

        client = MSGraphClient(config)
        pipeline = EmailIngestionPipeline(graph_client=client)

        dept_mapping = {
            "@brookergroup.com": "cac",
            # Add more mappings as needed
        }

        results = await pipeline.run_ingestion_cycle(dept_mapping)

        return {
            "status": "completed",
            "emails_processed": len(results),
            "bodies_ingested": sum(1 for r in results if r.body_ingested),
            "attachments_ingested": sum(r.attachments_ingested for r in results),
            "errors": sum(len(r.errors) for r in results),
        }
    except ImportError:
        return {"status": "skipped", "reason": "Email ingestion modules not available"}


# ---------------------------------------------------------------------------
# Fix 4 — nlq_engine endpoint
# ---------------------------------------------------------------------------

@router.post("/nlq")
@limiter.limit("20/minute")
async def natural_language_query(request: Request):
    """Parse a natural language query into structured data."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    body = await request.json()
    query = body.get("query", "")
    if not query:
        raise HTTPException(400, "query field required")

    try:
        from services.shared.nlq_engine import parse_nlq
        result = parse_nlq(query)

        response = {
            "original_query": result.original_query,
            "query_type": result.query_type,
            "parameters": result.parameters,
            "explanation": result.explanation,
        }

        # If we got a SQL query and it's safe, execute it
        if result.sql_query and result.query_type == "metric_lookup":
            try:
                db = request.app.state.db_pool
                async with db.acquire() as conn:
                    rows = await conn.fetch(result.sql_query)
                    response["data"] = [dict(r) for r in rows]
            except Exception as e:
                response["sql_error"] = str(e)

        return response
    except ImportError:
        raise HTTPException(501, "NLQ engine not available") from None


# ---------------------------------------------------------------------------
# Fix 5 — auto_approve endpoint
# ---------------------------------------------------------------------------

@router.post("/auto-approve/evaluate/{proposal_id}")
@limiter.limit("10/minute")
async def evaluate_auto_approve(proposal_id: int, request: Request):
    """Evaluate if a proposal qualifies for auto-approval."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    if claims.role not in ("admin", "ceo", "cto"):
        raise HTTPException(403, "Admin role required")

    try:
        from services.shared.auto_approve import evaluate_auto_approve

        db = request.app.state.db_pool
        async with db.acquire() as conn:
            proposal = await conn.fetchrow(
                "SELECT * FROM staging_proposals WHERE id = $1", proposal_id
            )
            if not proposal:
                raise HTTPException(404, "Proposal not found")

            # Currently no auto-approve rules configured
            # Rules would be loaded from a config table or file
            rules = []

            decision = await evaluate_auto_approve(dict(proposal), rules, conn)

            return {
                "proposal_id": proposal_id,
                "auto_approved": decision.auto_approved,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "historical_rate": decision.historical_rate,
            }
    except ImportError:
        raise HTTPException(501, "Auto-approve module not available") from None
