"""Synthesis node for HR -- formats final answer with citations.

Phase 2: includes detect_self_report call after response generation
for knowledge gap tracking.
"""
from __future__ import annotations

import re

import structlog

from ..tools.llm_client import LLMClient

# Strip any [N] citation markers the model may emit even when told not to.
_CITATION_RE = re.compile(r"\[\d+\]")

try:
    from services.shared.knowledge_gaps import detect_self_report
except ImportError:
    detect_self_report = None  # type: ignore[assignment]

try:
    from services.shared.citation_grounding import ground_citations, add_grounding_badges
except ImportError:
    ground_citations = None  # type: ignore[assignment]

from .grounding_gate import _MIN_RELEVANCE, abstain as _abstain

logger = structlog.get_logger("hr-orchestrator.synthesise")

SYSTEM_PROMPT = """\
You are an HR AI assistant for the Brooker Group Human Resources department.
Synthesise a clear, professional answer using the provided context and agent analysis.

Rules:
- Include source citations in [N] format referencing the provided sources.
- Quote KEY facts (status, control item number, Yes/No mark, date) verbatim
  from the source chunks — do not paraphrase the checklist marks.
- If a chunk has a "Quick-answer aliases" Q&A that matches the user's question,
  PREFER it — that's the canonical phrasing of the answer.
- Be precise and factual — never speculate. If no relevant chunks were retrieved,
  say so. Do not invent compensation or headcount figures.
- Include any escalation warnings if present.
- Keep the response concise but complete.
- NEVER propose data changes -- HR is read-only."""


def _confidence_label(score: float) -> str:
    """Map confidence score to human-readable label."""
    if score >= 0.85:
        return "High"
    elif score >= 0.60:
        return "Medium"
    return "Low"


async def synthesise_response(state: dict, *, llm_client: LLMClient, db_conn=None) -> dict:
    """Synthesise final answer with citations.

    Returns {"answer": str, "confidence": str, "response": str, "citations": list}.
    """
    context_text = state.get("context_text", "")
    agent_response = state.get("agent_response", "")
    escalation_triggered = state.get("escalation_triggered", False)
    escalation_detail = state.get("escalation_detail")
    confidence_score = state.get("confidence_score", 0.0)

    # Defence-in-depth: if grounding_gate already wrote a canned abstention
    # answer, return it immediately without calling the LLM.
    if not state.get("is_grounded", True):
        canned = _CITATION_RE.sub("", state.get("answer", "")).strip()
        logger.info("synthesise_abstention_passthrough", answer_preview=canned[:60])
        return {"answer": canned, "confidence": "Low", "response": canned, "citations": []}

    # Build user prompt with all context
    parts: list[str] = []

    if context_text:
        parts.append(f"Retrieved sources:\n{context_text}")
    else:
        parts.append("No relevant documents found in the knowledge base.")

    if agent_response:
        parts.append(f"Agent analysis:\n{agent_response}")

    if escalation_triggered and escalation_detail:
        parts.append(f"ESCALATION: {escalation_detail}")

    parts.append(f"Original question: {state.get('query', '')}")

    user_prompt = "\n\n".join(parts)

    try:
        answer = await llm_client.chat(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,  # was 0.2; lowered to reduce factual-recall flakiness
            max_tokens=2048,
        )
    except Exception as exc:
        logger.error("synthesise_failed", error=str(exc))
        answer = "I encountered an error while processing your question. Please try again."

    # Build gsources from RELEVANCE-PASSING chunks only — otherwise the backstop
    # tries to verify the LLM's citations against retrieval noise. Also skip the
    # backstop entirely on capability/conversational bypasses (answer comes from
    # the SKILL mandate, not from retrieved sources, so there's nothing legit to
    # verify against). See cac-orchestrator/nodes/synthesise.py for the same fix.
    is_bypass = bool(state.get("is_capability_bypass"))
    gsources = []
    for i, s in enumerate(state.get("sources", []), start=1):
        score = float(s.get("relevance_score") or s.get("score") or 0.0)
        if score < _MIN_RELEVANCE:
            continue
        gsources.append({
            "id": str(i),
            "text": s.get("text") or s.get("excerpt") or "",
            "source": s.get("filename") or s.get("type") or f"src{i}",
        })
    if ground_citations is not None and gsources and not is_bypass:
        report = ground_citations(answer, gsources)
        if report.total_citations > 0 and report.verified == 0:
            logger.warning(
                "synthesise_ungrounded_replaced",
                citations=report.total_citations,
                query_preview=state.get("query", "")[:80],
            )
            canned = _abstain(state.get("query", ""))
            return {
                "answer": canned,
                "confidence": "Low",
                "response": canned,
                "citations": [],
            }
        answer = add_grounding_badges(answer, report)

    # Phase 2: detect self-report knowledge gaps
    if detect_self_report is not None and db_conn is not None:
        try:
            await detect_self_report(
                response=answer,
                dept_id=state.get("dept_id", "hr"),
                agent_id=state.get("agent_id", state.get("agent_name", "hr-orchestrator")),
                query=state.get("query", ""),
                db_conn=db_conn,
            )
        except Exception as exc:
            logger.warning("detect_self_report_failed", error=str(exc))

    confidence = _confidence_label(confidence_score)

    # Defence-in-depth citation strip: if no sources were retrieved, remove any
    # [N] markers the model still emitted.
    if not state.get("sources"):
        answer = _CITATION_RE.sub("", answer).strip()

    # Build citations list from sources for daily_log compatibility
    citations = []
    for s in state.get("sources", []):
        label = s.get("filename", "unknown")
        if s.get("page"):
            label += f" p.{s['page']}"
        citations.append(label)

    logger.info("response_synthesised", confidence=confidence)
    return {
        "answer": answer,
        "confidence": confidence,
        "response": answer,  # alias for daily_log node
        "citations": citations,
    }
