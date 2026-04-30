"""Synthesis node for HR -- formats final answer with citations.

Phase 2: includes detect_self_report call after response generation
for knowledge gap tracking.
"""
from __future__ import annotations

import structlog

from ..tools.llm_client import LLMClient

try:
    from services.shared.knowledge_gaps import detect_self_report
except ImportError:
    detect_self_report = None  # type: ignore[assignment]

logger = structlog.get_logger("hr-orchestrator.synthesise")

SYSTEM_PROMPT = """\
You are an HR AI assistant for the Brooker Group Human Resources department.
Synthesise a clear, professional answer using the provided context and agent analysis.

Rules:
- Include source citations in [N] format referencing the provided sources
- Be precise and factual -- never speculate
- If no relevant sources were found, say so clearly
- Include any escalation warnings if present
- Keep the response concise but complete
- NEVER propose data changes -- HR is read-only"""


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
            temperature=0.2,
            max_tokens=2048,
        )
    except Exception as exc:
        logger.error("synthesise_failed", error=str(exc))
        answer = "I encountered an error while processing your question. Please try again."

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
