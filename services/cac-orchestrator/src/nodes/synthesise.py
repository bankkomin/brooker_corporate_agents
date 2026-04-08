"""Synthesis node — formats final answer with citations using Qwen 122B."""
from __future__ import annotations

import structlog

from ..tools.llm_client import LLMClient

logger = structlog.get_logger("cac-orchestrator.synthesise")

SYSTEM_PROMPT = """\
You are a corporate committee AI assistant for the Capital Allocation & ALCO Committee.
Synthesise a clear, professional answer using the provided context and agent analysis.

Rules:
- Include source citations in [N] format referencing the provided sources
- Be precise and factual — never speculate
- If no relevant sources were found, say so clearly
- Include any escalation warnings if present
- Mention the Excel navigation pointer if a change was proposed
- Keep the response concise but complete"""


def _confidence_label(score: float) -> str:
    """Map confidence score to human-readable label."""
    if score >= 0.85:
        return "High"
    elif score >= 0.60:
        return "Medium"
    return "Low"


async def synthesise_response(state: dict, *, llm_client: LLMClient) -> dict:
    """Synthesise final answer with citations.

    Returns {"answer": str, "confidence": str}.
    """
    context_text = state.get("context_text", "")
    agent_response = state.get("agent_response", "")
    excel_nav = state.get("excel_nav")
    escalation_triggered = state.get("escalation_triggered", False)
    escalation_detail = state.get("escalation_detail")
    staging_proposal_id = state.get("staging_proposal_id")
    validation_warnings = state.get("validation_warnings", [])
    confidence_score = state.get("confidence_score", 0.0)

    # Build user prompt with all context
    parts: list[str] = []

    if context_text:
        parts.append(f"Retrieved sources:\n{context_text}")
    else:
        parts.append("No relevant documents found in the knowledge base.")

    if agent_response:
        parts.append(f"Agent analysis:\n{agent_response}")

    if excel_nav:
        parts.append(f"Excel reference: {excel_nav}")

    if staging_proposal_id:
        parts.append(
            f"A change proposal ({staging_proposal_id}) has been created for human approval."
        )

    if escalation_triggered and escalation_detail:
        parts.append(f"ESCALATION: {escalation_detail}")

    if validation_warnings:
        parts.append(f"Validation notes: {'; '.join(validation_warnings)}")

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

    confidence = _confidence_label(confidence_score)
    has_proposal = staging_proposal_id is not None
    logger.info("response_synthesised", confidence=confidence, has_proposal=has_proposal)
    return {"answer": answer, "confidence": confidence}
