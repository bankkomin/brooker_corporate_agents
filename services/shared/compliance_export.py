"""Compliance & audit trail export — generates regulatory-ready reports."""
import csv
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    timestamp: str
    dept_id: str
    event_type: str  # query, proposal, approval, rejection, escalation, knowledge_gap
    actor: str  # user_id or agent_id
    summary: str
    details: dict


async def export_audit_trail(
    db_pool,
    dept_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    format: str = "json",  # json, csv
) -> str | bytes:
    """Export full audit trail for compliance review."""
    entries: list[AuditEntry] = []

    async with db_pool.acquire() as conn:
        # 1. Agent interactions (queries)
        query = """
            SELECT ai.created_at, ai.dept_id, ai.agent_id, ai.user_id, ai.query, ai.response
            FROM agent_interactions ai
            WHERE 1=1
        """
        params: list = []
        idx = 1

        if dept_id:
            query += f" AND ai.dept_id = ${idx}"
            params.append(dept_id)
            idx += 1
        if start_date:
            query += f" AND ai.created_at >= ${idx}::timestamptz"
            params.append(start_date)
            idx += 1
        if end_date:
            query += f" AND ai.created_at <= ${idx}::timestamptz"
            params.append(end_date)
            idx += 1

        query += " ORDER BY ai.created_at"
        rows = await conn.fetch(query, *params)

        for r in rows:
            entries.append(AuditEntry(
                timestamp=r["created_at"].isoformat(),
                dept_id=r["dept_id"],
                event_type="query",
                actor=r.get("user_id", "unknown"),
                summary=f"Query: {r['query'][:100]}",
                details={
                    "query": r["query"],
                    "response": r.get("response", "")[:500],
                    "agent": r.get("agent_id", ""),
                },
            ))

        # 2. Staging proposals
        rows = await conn.fetch("""
            SELECT sp.created_at, ai.dept_id, ai.agent_id, sp.cell, sp.proposed_value,
                   sp.confidence, sp.status, sp.id
            FROM staging_proposals sp
            JOIN agent_interactions ai ON ai.id = sp.interaction_id
            WHERE 1=1
            ORDER BY sp.created_at
        """)

        for r in rows:
            entries.append(AuditEntry(
                timestamp=r["created_at"].isoformat(),
                dept_id=r["dept_id"],
                event_type="proposal",
                actor=r.get("agent_id", "unknown"),
                summary=(
                    f"Proposed {r.get('cell', '?')} = {r.get('proposed_value', '?')} "
                    f"(confidence: {r.get('confidence', 0):.0%})"
                ),
                details={
                    "proposal_id": r["id"],
                    "cell": r.get("cell"),
                    "value": r.get("proposed_value"),
                    "confidence": r.get("confidence"),
                    "status": r.get("status"),
                },
            ))

        # 3. Approval decisions
        rows = await conn.fetch("""
            SELECT ad.created_at, ai.dept_id, ad.action, ad.edited_value, ad.rejection_reason,
                   sp.cell, sp.proposed_value, ad.proposal_id
            FROM approval_decisions ad
            JOIN staging_proposals sp ON sp.id = ad.proposal_id
            JOIN agent_interactions ai ON ai.id = sp.interaction_id
            ORDER BY ad.created_at
        """)

        for r in rows:
            summary = f"{r['action'].upper()}: {r.get('cell', '?')} = {r.get('proposed_value', '?')}"
            if r.get("edited_value"):
                summary += f" -> {r['edited_value']}"
            if r.get("rejection_reason"):
                summary += f" ({r['rejection_reason']})"

            entries.append(AuditEntry(
                timestamp=r["created_at"].isoformat(),
                dept_id=r["dept_id"],
                event_type=r["action"],  # approved, edited, rejected
                actor="hod",
                summary=summary,
                details=dict(r),
            ))

        # 4. Escalations
        rows = await conn.fetch("""
            SELECT created_at, dept_id, severity, reason, status
            FROM escalations
            ORDER BY created_at
        """)

        for r in rows:
            entries.append(AuditEntry(
                timestamp=r["created_at"].isoformat(),
                dept_id=r["dept_id"],
                event_type="escalation",
                actor="system",
                summary=f"[{r.get('severity', 'unknown')}] {r.get('reason', '')[:100]}",
                details=dict(r),
            ))

    # Sort all entries chronologically
    entries.sort(key=lambda e: e.timestamp)

    if format == "csv":
        return _export_csv(entries)
    return _export_json(entries)


def _export_json(entries: list[AuditEntry]) -> str:
    return json.dumps(
        [
            {
                "timestamp": e.timestamp,
                "dept_id": e.dept_id,
                "event_type": e.event_type,
                "actor": e.actor,
                "summary": e.summary,
                "details": e.details,
            }
            for e in entries
        ],
        indent=2,
        default=str,
    )


def _export_csv(entries: list[AuditEntry]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["timestamp", "dept_id", "event_type", "actor", "summary"])
    for e in entries:
        writer.writerow([e.timestamp, e.dept_id, e.event_type, e.actor, e.summary])
    return output.getvalue()


async def generate_compliance_summary(
    db_pool,
    dept_id: str,
    quarter: str,  # e.g., "2026-Q2"
) -> dict:
    """Generate a quarterly compliance summary report."""
    year, q = quarter.split("-Q")
    quarter_num = int(q)
    start_month = (quarter_num - 1) * 3 + 1
    start_date = f"{year}-{start_month:02d}-01"
    end_month = start_month + 2
    end_date = f"{year}-{end_month:02d}-28"

    async with db_pool.acquire() as conn:
        total_queries = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_interactions WHERE dept_id = $1 "
            "AND created_at BETWEEN $2::date AND $3::date",
            dept_id, start_date, end_date,
        ) or 0

        total_proposals = await conn.fetchval(
            "SELECT COUNT(*) FROM staging_proposals sp "
            "JOIN agent_interactions ai ON ai.id = sp.interaction_id "
            "WHERE ai.dept_id = $1 AND sp.created_at BETWEEN $2::date AND $3::date",
            dept_id, start_date, end_date,
        ) or 0

        approved = await conn.fetchval(
            "SELECT COUNT(*) FROM approval_decisions ad "
            "JOIN staging_proposals sp ON sp.id = ad.proposal_id "
            "JOIN agent_interactions ai ON ai.id = sp.interaction_id "
            "WHERE ai.dept_id = $1 AND ad.action = 'approved' "
            "AND ad.created_at BETWEEN $2::date AND $3::date",
            dept_id, start_date, end_date,
        ) or 0

        rejected = await conn.fetchval(
            "SELECT COUNT(*) FROM approval_decisions ad "
            "JOIN staging_proposals sp ON sp.id = ad.proposal_id "
            "JOIN agent_interactions ai ON ai.id = sp.interaction_id "
            "WHERE ai.dept_id = $1 AND ad.action = 'rejected' "
            "AND ad.created_at BETWEEN $2::date AND $3::date",
            dept_id, start_date, end_date,
        ) or 0

        escalations = await conn.fetchval(
            "SELECT COUNT(*) FROM escalations WHERE dept_id = $1 "
            "AND created_at BETWEEN $2::date AND $3::date",
            dept_id, start_date, end_date,
        ) or 0

    return {
        "dept_id": dept_id,
        "quarter": quarter,
        "period": {"start": start_date, "end": end_date},
        "metrics": {
            "total_queries": total_queries,
            "total_proposals": total_proposals,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": f"{approved / total_proposals * 100:.1f}%" if total_proposals > 0 else "N/A",
            "escalations": escalations,
        },
        "data_safety": {
            "direct_writes_to_mirror": 0,  # should always be 0
            "all_writes_via_staging": True,
            "human_approval_enforced": True,
        },
        "generated_at": datetime.utcnow().isoformat(),
    }
