"""Structured report generator — weekly briefs, meeting prep, committee summaries."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


@dataclass
class ReportSection:
    title: str
    content: str
    data: dict | None = None  # structured data for charts/tables
    priority: str = "medium"  # high, medium, low


@dataclass
class Report:
    report_type: str  # weekly_brief, meeting_prep, committee_summary
    dept_id: str
    title: str
    generated_at: datetime
    period_start: str
    period_end: str
    sections: list[ReportSection] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


async def generate_weekly_brief(
    dept_id: str,
    dept_name: str,
    db_pool,
    period_days: int = 7,
) -> Report:
    """Generate a weekly department brief."""
    now = datetime.utcnow()
    start = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")

    report = Report(
        report_type="weekly_brief",
        dept_id=dept_id,
        title=f"{dept_name} Weekly Brief — {start} to {end}",
        generated_at=now,
        period_start=start,
        period_end=end,
    )

    async with db_pool.acquire() as conn:
        # Key metrics
        interactions = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_interactions WHERE dept_id = $1 AND created_at > NOW() - make_interval(days => $2)",
            dept_id, period_days,
        ) or 0

        proposals = await conn.fetchval(
            "SELECT COUNT(*) FROM staging_proposals sp JOIN agent_interactions ai ON ai.id = sp.interaction_id WHERE ai.dept_id = $1 AND sp.created_at > NOW() - make_interval(days => $2)",
            dept_id, period_days,
        ) or 0

        approved = await conn.fetchval(
            "SELECT COUNT(*) FROM approval_decisions ad JOIN staging_proposals sp ON sp.id = ad.proposal_id JOIN agent_interactions ai ON ai.id = sp.interaction_id WHERE ai.dept_id = $1 AND ad.action = 'approved' AND ad.created_at > NOW() - make_interval(days => $2)",
            dept_id, period_days,
        ) or 0

        rejected = await conn.fetchval(
            "SELECT COUNT(*) FROM approval_decisions ad JOIN staging_proposals sp ON sp.id = ad.proposal_id JOIN agent_interactions ai ON ai.id = sp.interaction_id WHERE ai.dept_id = $1 AND ad.action = 'rejected' AND ad.created_at > NOW() - make_interval(days => $2)",
            dept_id, period_days,
        ) or 0

        gaps = await conn.fetchval(
            "SELECT COUNT(*) FROM agent_knowledge_gaps WHERE dept_id = $1 AND created_at > NOW() - make_interval(days => $2) AND resolved_at IS NULL",
            dept_id, period_days,
        ) or 0

        escalations = await conn.fetchval(
            "SELECT COUNT(*) FROM escalations WHERE dept_id = $1 AND created_at > NOW() - make_interval(days => $2)",
            dept_id, period_days,
        ) or 0

    # Activity summary
    approval_rate = (approved / proposals * 100) if proposals > 0 else 0
    report.sections.append(ReportSection(
        title="Activity Summary",
        content=(
            f"- Total queries: {interactions}\n"
            f"- Staging proposals: {proposals}\n"
            f"- Approved: {approved} ({approval_rate:.0f}%)\n"
            f"- Rejected: {rejected}\n"
            f"- Escalations: {escalations}\n"
            f"- Knowledge gaps (unresolved): {gaps}"
        ),
        data={"interactions": interactions, "proposals": proposals, "approved": approved, "rejected": rejected, "gaps": gaps},
        priority="high",
    ))

    # Knowledge gaps
    if gaps > 0:
        async with db_pool.acquire() as conn:
            gap_rows = await conn.fetch(
                "SELECT query, hit_count FROM agent_knowledge_gaps WHERE dept_id = $1 AND resolved_at IS NULL ORDER BY created_at DESC LIMIT 5",
                dept_id,
            )
        gap_text = "\n".join(f"- \"{r['query'][:80]}\" (hits: {r['hit_count']})" for r in gap_rows)
        report.sections.append(ReportSection(
            title="Knowledge Gaps — Documents Needed",
            content=f"The agent couldn't find sufficient data for these queries:\n{gap_text}",
            priority="high" if gaps > 3 else "medium",
        ))

    # Escalations
    if escalations > 0:
        report.sections.append(ReportSection(
            title="Escalations",
            content=f"{escalations} escalation(s) raised this period. Review in the approval dashboard.",
            priority="high",
        ))

    return report


async def generate_meeting_prep(
    dept_id: str,
    dept_name: str,
    meeting_date: str,
    db_pool,
) -> Report:
    """Generate a pre-meeting preparation document."""
    now = datetime.utcnow()

    report = Report(
        report_type="meeting_prep",
        dept_id=dept_id,
        title=f"{dept_name} Committee Meeting Prep — {meeting_date}",
        generated_at=now,
        period_start=(now - timedelta(days=30)).strftime("%Y-%m-%d"),
        period_end=meeting_date,
    )

    async with db_pool.acquire() as conn:
        # Pending proposals
        pending = await conn.fetch(
            """SELECT sp.id, sp.cell, sp.proposed_value, sp.confidence, ai.agent_id
               FROM staging_proposals sp
               JOIN agent_interactions ai ON ai.id = sp.interaction_id
               WHERE ai.dept_id = $1 AND sp.status = 'pending'
               ORDER BY sp.created_at DESC LIMIT 10""",
            dept_id,
        )

        # Recent decisions
        recent = await conn.fetch(
            """SELECT sp.cell, sp.proposed_value, ad.action, ad.edited_value, ad.rejection_reason
               FROM approval_decisions ad
               JOIN staging_proposals sp ON sp.id = ad.proposal_id
               JOIN agent_interactions ai ON ai.id = sp.interaction_id
               WHERE ai.dept_id = $1 AND ad.created_at > NOW() - INTERVAL '30 days'
               ORDER BY ad.created_at DESC LIMIT 10""",
            dept_id,
        )

    # Pending items
    if pending:
        items = "\n".join(
            f"- Cell {r['cell']}: proposed {r['proposed_value']} (confidence: {r['confidence']:.0%}) by {r['agent_id']}"
            for r in pending
        )
        report.sections.append(ReportSection(
            title="Pending Proposals for Review",
            content=f"{len(pending)} proposal(s) awaiting decision:\n{items}",
            priority="high",
        ))

    # Recent activity
    if recent:
        items = "\n".join(
            f"- {r['cell']}: {r['action']}" + (f" → {r['edited_value']}" if r['edited_value'] else "") + (f" ({r['rejection_reason']})" if r['rejection_reason'] else "")
            for r in recent
        )
        report.sections.append(ReportSection(
            title="Recent Decisions (Last 30 Days)",
            content=items,
            priority="medium",
        ))

    return report
