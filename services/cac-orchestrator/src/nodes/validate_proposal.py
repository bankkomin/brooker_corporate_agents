"""Proposal validation node — independent LLM review + history cross-check."""
from __future__ import annotations

import json

import structlog

from ..tools.db_client import DBClient
from ..tools.llm_client import LLMClient

logger = structlog.get_logger("cac-orchestrator.validate")

VALIDATION_PROMPT = """\
You are a proposal reviewer for a Capital Allocation committee AI system.
Your job is to validate that a proposed spreadsheet change is correct \
before it goes to a human for approval.

Proposed change:
- Cell: {cell}
- Old value: {old_value}
- New value: {new_value}
- Agent reasoning: {reasoning}
- Source excerpt: {source_excerpt}
- Excel navigation: {excel_nav}
{history_section}

Check these items:
1. SOURCE ACCURACY: Does the new_value actually appear in or follow from \
the source_excerpt? Flag if the value seems hallucinated.
2. CELL VALIDITY: Does the cell reference make sense for this type of data \
given the Excel navigation context?
3. REASONING SOUNDNESS: Does the reasoning logically follow from the source?
4. CONTRADICTIONS: Does this contradict any information in the source or \
recent proposals?

Respond with JSON only:
{{"passed": true/false, "confidence_adjustment": 0.0, \
"warnings": [], "blocking_reason": null}}

- Set passed=false and blocking_reason if there's a clear error
- Set confidence_adjustment to a negative number (e.g., -0.1) if borderline
- Add warnings for minor concerns that don't block the proposal"""


async def validate_proposal(
    state: dict,
    *,
    llm_client: LLMClient,
    db_client: DBClient,
) -> dict:
    """Validate a proposed change before staging.

    Returns dict with validation_passed, validation_warnings, confidence_score.
    """
    proposed_value = state.get("proposed_value")
    proposed_cell = state.get("proposed_cell")
    confidence_score = state.get("confidence_score", 0.0)

    if not proposed_value or not proposed_cell:
        return {
            "validation_passed": True, "validation_warnings": [],
            "confidence_score": confidence_score,
        }

    # History cross-check
    file = state.get("file", "ALCO_Tracker.xlsx")
    tab = state.get("tab", "")
    recent = await db_client.get_recent_proposals_for_cell(file, tab, proposed_cell)

    history_section = ""
    if recent:
        history_lines = []
        for p in recent[:3]:  # Last 3 proposals
            created = p.get("created_at", "unknown")
            agent = p.get("agent", "?")
            val = p.get("new_value", "?")
            conf = p.get("confidence", "?")
            st = p.get("status", "?")
            history_lines.append(
                f"- {created}: {agent} proposed "
                f"'{val}' (confidence: {conf}, status: {st})"
            )
        history_section = "\nRecent proposals for the same cell:\n" + "\n".join(history_lines)

    prompt = VALIDATION_PROMPT.format(
        cell=proposed_cell,
        old_value=state.get("old_value", "(empty)"),
        new_value=proposed_value,
        reasoning=state.get("agent_response", ""),
        source_excerpt=state.get("context_text", "")[:500],
        excel_nav=state.get("excel_nav", ""),
        history_section=history_section,
    )

    try:
        raw = await llm_client.chat(
            [{"role": "system", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
        result = json.loads(raw)
        passed = bool(result.get("passed", True))
        adjustment = float(result.get("confidence_adjustment", 0.0))
        warnings = list(result.get("warnings", []))
        blocking_reason = result.get("blocking_reason")

        if not passed and blocking_reason:
            warnings.append(f"BLOCKED: {blocking_reason}")

        adjusted_confidence = confidence_score + adjustment

        logger.info(
            "proposal_validated",
            passed=passed,
            adjustment=adjustment,
            warnings=warnings,
            original_confidence=confidence_score,
            adjusted_confidence=adjusted_confidence,
        )
        return {
            "validation_passed": passed,
            "validation_warnings": warnings,
            "confidence_score": adjusted_confidence,
        }
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("validation_parse_error_blocking", error=str(exc))
        return {
            "validation_passed": False,
            "validation_warnings": [f"BLOCKED: Validation unparseable: {exc}"],
            "confidence_score": confidence_score * 0.5,
        }
