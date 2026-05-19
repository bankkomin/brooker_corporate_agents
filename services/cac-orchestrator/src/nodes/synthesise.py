"""Synthesis node — formats final answer with citations using Qwen 122B.

Phase 2: integrates knowledge gap detection via shared library.
"""
from __future__ import annotations

import structlog

from ..tools.llm_client import LLMClient

try:
    from services.shared.knowledge_gaps import detect_self_report
except ImportError:
    detect_self_report = None  # type: ignore[assignment]

try:
    from services.shared.citation_grounding import add_grounding_badges, ground_citations
except ImportError:
    ground_citations = None

try:
    from services.shared.calibrated_confidence import compute_confidence
except ImportError:
    compute_confidence = None

try:
    from services.shared.chain_of_thought import (
        build_cot_prompt,
        classify_complexity,
        parse_cot_response,
    )
except ImportError:
    classify_complexity = None

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

    # Chain-of-thought for complex queries
    query = state.get("query", "")
    use_cot = False
    query_type = "simple"
    if classify_complexity is not None:
        query_type = classify_complexity(query)
        if query_type != "simple":
            use_cot = True
            user_prompt = build_cot_prompt(query, query_type, context_text, skill_content="")

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

    # Parse structured CoT response if chain-of-thought was used
    if use_cot and parse_cot_response is not None:
        cot_result = parse_cot_response(answer, query, query_type)
        # Use the final answer from CoT parsing
        if cot_result.final_answer:
            answer = cot_result.final_answer

    # Citation grounding
    if ground_citations is not None:
        sources = state.get("retrieved_sources", [])
        grounding_report = ground_citations(answer, sources)
        answer = add_grounding_badges(answer, grounding_report)
        # Use grounding accuracy for calibrated confidence
        citation_accuracy = grounding_report.accuracy
    else:
        citation_accuracy = 1.0

    # Calibrated confidence (replaces LLM self-reported score)
    if compute_confidence is not None:
        retrieved_chunks = state.get("retrieved_chunks", [])
        top_sim = state.get("top_similarity", 0.0)
        proposed = state.get("proposed_value")
        conf = compute_confidence(
            retrieved_chunks=retrieved_chunks,
            top_similarity=top_sim,
            answer_text=answer,
            proposed_value=proposed,
            citation_accuracy=citation_accuracy,
        )
        confidence_score = conf.composite

    confidence = _confidence_label(confidence_score)
    has_proposal = staging_proposal_id is not None

    # Phase 2: detect knowledge gaps from LLM self-report phrases
    if detect_self_report is not None:
        try:

            # detect_self_report needs a db connection; use a no-op if unavailable
            dept_id = state.get("dept_id", "cac")
            agent_id = state.get("agent_id", state.get("agent_name", "cac-orchestrator"))
            query = state.get("query", "")

            # Try to get a db connection from the db_client if available
            # detect_self_report is async so we import and call it
            gap_detected = False
            try:
                # The db_conn parameter in detect_self_report expects an
                # asyncpg connection. We pass None if unavailable — the
                # function will handle the exception internally.
                gap_detected = await detect_self_report(
                    response=answer,
                    dept_id=dept_id,
                    agent_id=agent_id,
                    query=query,
                    db_conn=None,  # Will be wired to real pool in future iteration
                )
            except Exception as gap_exc:
                logger.debug("knowledge_gap_detect_call_failed", error=str(gap_exc))

            if gap_detected:
                logger.info("knowledge_gap_self_report_detected", query=query[:80])
        except Exception as exc:
            logger.debug("knowledge_gap_integration_skipped", error=str(exc))

    logger.info("response_synthesised", confidence=confidence, has_proposal=has_proposal)
    return {"answer": answer, "confidence": confidence}
