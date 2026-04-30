"""Auto-approve pipeline for proposals that meet strict accuracy criteria."""
import logging
import re
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class AutoApproveRule:
    dept_id: str
    cell_pattern: str  # regex or exact cell reference
    min_historical_approval_rate: float  # e.g., 0.95
    min_sample_size: int  # minimum proposals to have data on
    min_confidence: float  # minimum calibrated confidence
    enabled: bool


@dataclass
class AutoApproveDecision:
    proposal_id: str
    dept_id: str
    cell: str
    auto_approved: bool
    reason: str
    rule_matched: str | None
    confidence: float
    historical_rate: float | None


# Default rules — extremely conservative
DEFAULT_RULES = [
    # Example: CAC LCR cell is approved >95% of the time with >30 samples
    # These would be populated from 6+ months of approval data
]


async def evaluate_auto_approve(
    proposal: dict,
    rules: list[AutoApproveRule],
    db_conn,
) -> AutoApproveDecision:
    """Evaluate whether a proposal qualifies for auto-approval."""
    dept_id = proposal.get("dept_id", "")
    cell = proposal.get("cell", "")
    confidence = proposal.get("confidence", 0.0)
    proposal_id = proposal.get("id", "")

    # Find matching rule
    matching_rule = None
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.dept_id != dept_id:
            continue
        if re.match(rule.cell_pattern, cell):
            matching_rule = rule
            break

    if not matching_rule:
        return AutoApproveDecision(
            proposal_id=proposal_id,
            dept_id=dept_id,
            cell=cell,
            auto_approved=False,
            reason="No matching auto-approve rule",
            rule_matched=None,
            confidence=confidence,
            historical_rate=None,
        )

    # Check confidence threshold
    if confidence < matching_rule.min_confidence:
        return AutoApproveDecision(
            proposal_id=proposal_id,
            dept_id=dept_id,
            cell=cell,
            auto_approved=False,
            reason=f"Confidence {confidence:.2f} below threshold {matching_rule.min_confidence}",
            rule_matched=matching_rule.cell_pattern,
            confidence=confidence,
            historical_rate=None,
        )

    # Check historical approval rate
    historical = await _get_historical_rate(db_conn, dept_id, cell)

    if historical is None or historical["sample_size"] < matching_rule.min_sample_size:
        return AutoApproveDecision(
            proposal_id=proposal_id,
            dept_id=dept_id,
            cell=cell,
            auto_approved=False,
            reason=f"Insufficient historical data ({historical['sample_size'] if historical else 0} samples, need {matching_rule.min_sample_size})",
            rule_matched=matching_rule.cell_pattern,
            confidence=confidence,
            historical_rate=historical["rate"] if historical else None,
        )

    if historical["rate"] < matching_rule.min_historical_approval_rate:
        return AutoApproveDecision(
            proposal_id=proposal_id,
            dept_id=dept_id,
            cell=cell,
            auto_approved=False,
            reason=f"Historical approval rate {historical['rate']:.2f} below threshold {matching_rule.min_historical_approval_rate}",
            rule_matched=matching_rule.cell_pattern,
            confidence=confidence,
            historical_rate=historical["rate"],
        )

    # All checks passed — auto-approve
    log.info(
        "Auto-approving proposal %s: cell=%s, confidence=%.2f, historical_rate=%.2f",
        proposal_id, cell, confidence, historical["rate"],
    )

    return AutoApproveDecision(
        proposal_id=proposal_id,
        dept_id=dept_id,
        cell=cell,
        auto_approved=True,
        reason=f"Passed all checks: confidence={confidence:.2f}, historical_rate={historical['rate']:.2f}, samples={historical['sample_size']}",
        rule_matched=matching_rule.cell_pattern,
        confidence=confidence,
        historical_rate=historical["rate"],
    )


async def _get_historical_rate(db_conn, dept_id: str, cell: str) -> dict | None:
    """Get historical approval rate for a specific cell."""
    if db_conn is None:
        return None

    try:
        row = await db_conn.fetchrow("""
            SELECT
                COUNT(*) as sample_size,
                COUNT(CASE WHEN ad.action = 'approved' THEN 1 END)::float / NULLIF(COUNT(*), 0) as rate
            FROM staging_proposals sp
            JOIN approval_decisions ad ON ad.proposal_id = sp.id
            WHERE sp.dept_id = $1 AND sp.cell = $2
              AND ad.created_at > NOW() - INTERVAL '6 months'
        """, dept_id, cell)

        if row and row["sample_size"] > 0:
            return {"sample_size": row["sample_size"], "rate": float(row["rate"])}
    except Exception:
        log.exception("Failed to fetch historical approval rate")

    return None
