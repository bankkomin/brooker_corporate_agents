"""Synthesis node — formats final answer with citations using Qwen 122B.

Phase 2: integrates knowledge gap detection via shared library.
"""
from __future__ import annotations

import re

import structlog

from ..tools.llm_client import LLMClient

# Strip any [N] citation markers the model may emit even when told not to.
# Applied as a last-resort defence when a turn was not grounded.
_CITATION_RE = re.compile(r"\[\d+\]")

# Shown when an answer cites sources but none of them actually support its
# claims — i.e. the model fabricated figures and attached citations that don't
# back them. Kept identical to grounding_gate's message for a consistent voice.
_ABSTENTION_ANSWER = (
    "I don't have reference material on this topic in my knowledge base yet. "
    "Please share a relevant document or data source and I'll analyse it."
)

try:
    from services.shared.knowledge_gaps import detect_self_report
except ImportError:
    detect_self_report = None  # type: ignore[assignment]

try:
    from services.shared.citation_grounding import add_grounding_badges, ground_citations
except ImportError:
    ground_citations = None

try:
    from services.shared.chain_of_thought import (
        build_cot_prompt,
        classify_complexity,
        parse_cot_response,
    )
except ImportError:
    classify_complexity = None
    build_cot_prompt = None  # type: ignore[assignment]
    parse_cot_response = None  # type: ignore[assignment]

logger = structlog.get_logger("cac-orchestrator.synthesise")

SYSTEM_PROMPT = """\
You are a corporate committee AI assistant for the Capital Allocation & ALCO Committee.
Synthesise a clear, professional answer using the provided context and agent analysis.

Rules:
- For substantive committee questions: include source citations in [N] format
  referencing the provided sources. Be precise and factual — never speculate
  beyond the sources.
- For greetings, small talk, or meta-questions about your capabilities (e.g.
  "hi", "hello", "what can you do?"): reply conversationally in 1-2 sentences.
  Briefly mention you cover liquidity, capital, ALM, funding, and covenant
  topics for the CAC. Do NOT say "no documents found" for these.
- For substantive questions where no sources were retrieved: say you don't have
  reference material for that topic and suggest the user share a relevant doc.
  Do NOT fabricate facts or cite sources that weren't provided.
- Include any escalation warnings if present.
- Mention the Excel navigation pointer if a change was proposed.
- Keep the response concise but complete."""


def _confidence_label(score: float) -> str:
    """Map confidence score to human-readable label."""
    if score >= 0.85:
        return "High"
    elif score >= 0.60:
        return "Medium"
    return "Low"


async def synthesise_response(state: dict, *, llm_client: LLMClient,
                              db_client=None) -> dict:
    """Synthesise final answer with citations.

    Returns {"answer": str, "confidence": str}.
    """
    context_text = state.get("context_text", "")
    attached_files_text = state.get("attached_files_text", "")
    agent_response = state.get("agent_response", "")
    excel_nav = state.get("excel_nav")
    escalation_triggered = state.get("escalation_triggered", False)
    escalation_detail = state.get("escalation_detail")
    staging_proposal_id = state.get("staging_proposal_id")
    validation_warnings = state.get("validation_warnings", [])
    # Prefer the calibrated score computed by calibrate_confidence (audit bug #3):
    # that value already drove the staging gate, so this label is consistent.
    confidence_score: float = state.get(
        "calibrated_confidence_score",
        state.get("confidence_score", 0.0),
    )

    # Defence-in-depth: if grounding_gate already set a canned abstention answer,
    # return it immediately without calling the LLM.  Also strip any [N] markers
    # that may have survived from a prior turn's state residue.
    if not state.get("is_grounded", True):
        canned = _CITATION_RE.sub("", state.get("answer", "")).strip()
        logger.info("synthesise_abstention_passthrough", answer_preview=canned[:60])
        return {"answer": canned, "confidence": "Low"}

    # Build user prompt with all context
    parts: list[str] = []

    if attached_files_text:
        parts.append(
            "Files attached to this turn (user-uploaded, treat as ground truth "
            "for what they describe):\n"
            f"{attached_files_text}"
        )

    if context_text:
        parts.append(f"Retrieved sources:\n{context_text}")
    elif not attached_files_text:
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

    # retrieve_context writes the key `sources` (not `retrieved_sources`) and
    # each source uses {filename, page, excerpt, relevance_score, type, ...}.
    # ground_citations expects {id, text, source} keyed by 1-based position.
    # Normalize once so the grounding helper can do its job.
    raw_sources = state.get("sources", []) or []
    grounding_sources: list[dict] = []
    top_sim = 0.0
    for i, s in enumerate(raw_sources, start=1):
        text = s.get("text") or s.get("excerpt") or ""
        grounding_sources.append({
            "id": str(i),
            "text": text,
            "source": s.get("filename") or s.get("type") or f"src{i}",
        })
        score = float(s.get("relevance_score") or s.get("score") or 0.0)
        if score > top_sim:
            top_sim = score

    # Citation grounding
    if ground_citations is not None:
        grounding_report = ground_citations(answer, grounding_sources)
        # Hard backstop: an answer that cites sources but verifies NONE of them
        # is fabrication — the model invented claims (e.g. specific figures) and
        # attached citations that don't support them. A weakly-relevant chunk can
        # slip past grounding_gate; this catches the resulting hallucination and
        # replaces it with abstention rather than showing false data with a
        # "0/N verified" badge.
        if grounding_report.total_citations > 0 and grounding_report.verified == 0:
            logger.warning(
                "synthesise_ungrounded_replaced",
                citations=grounding_report.total_citations,
                query_preview=state.get("query", "")[:80],
            )
            return {"answer": _ABSTENTION_ANSWER, "confidence": "Low"}
        answer = add_grounding_badges(answer, grounding_report)
        citation_accuracy = grounding_report.accuracy
    else:
        citation_accuracy = 1.0

    # Defence-in-depth citation strip: if no sources passed the relevance bar and
    # the user sent no attachments, remove any [N] markers the model still emitted.
    # grounding_gate already blocks this path for substantive queries, but this
    # catches edge cases where is_grounded was True (e.g. conversational query
    # that somehow generated inline citations).
    if not grounding_sources and not attached_files_text:
        answer = _CITATION_RE.sub("", answer).strip()

    # confidence_score already holds the pre-calibrated value read at the top of
    # this function (audit bug #3).  We no longer recompute here so that the
    # label displayed to the user matches the score that drove the staging gate.
    confidence = _confidence_label(confidence_score)
    has_proposal = staging_proposal_id is not None

    # Phase 2: detect knowledge gaps from LLM self-report phrases.
    # Audit bug #5 fix: acquire a real connection from db_client's pool
    # (was hardcoded to None, so every call hit AttributeError).
    if detect_self_report is not None and db_client is not None and getattr(db_client, "_pool", None) is not None:
        try:
            dept_id = state.get("dept_id", "cac")
            agent_id = state.get("agent_id", state.get("agent_name", "cac-orchestrator"))
            query = state.get("query", "")
            async with db_client._pool.acquire() as conn:
                gap_detected = await detect_self_report(
                    response=answer,
                    dept_id=dept_id,
                    agent_id=agent_id,
                    query=query,
                    db_conn=conn,
                )
            if gap_detected:
                logger.info("knowledge_gap_self_report_detected", query=query[:80])
        except Exception as exc:
            logger.debug("knowledge_gap_integration_skipped", error=str(exc))

    logger.info("response_synthesised", confidence=confidence, has_proposal=has_proposal)
    return {"answer": answer, "confidence": confidence}
