"""Grounding gate — hard-blocks ungrounded substantive answers.

Why this node exists
--------------------
The synthesise node instructs the LLM not to fabricate when there are no
sources. That is probabilistic. This gate makes abstention deterministic by
never invoking specialist agents or the LLM synthesiser when there is nothing
to ground an answer on.

Decision logic (evaluated after retrieve_context):
  grounded = at least one source with relevance_score >= RAG_MIN_RELEVANCE
           OR user attached files this turn
  conversational = short greeting / capability query (reply normally regardless)

  if conversational  -> pass through (is_grounded=True so synthesise calls LLM)
  if grounded        -> pass through
  else               -> short-circuit: write canned abstention answer, skip agents
"""
from __future__ import annotations

import os
import re

import structlog

logger = structlog.get_logger("hr-orchestrator.grounding_gate")

_DEFAULT_MIN_RELEVANCE: float = 0.50
_MIN_RELEVANCE: float = float(os.getenv("RAG_MIN_RELEVANCE", str(_DEFAULT_MIN_RELEVANCE)))

_ABSTENTION_ANSWER = (
    "I don't have reference material on this topic in my knowledge base yet. "
    "Please share a relevant document or data source and I'll analyse it."
)

_CONVERSATIONAL_RE = re.compile(
    r"^("
    r"hi|hello|hey|good morning|good afternoon|good evening|"
    r"how are you|what can you do|what do you do|"
    r"help|capabilities|what are your capabilities|"
    r"who are you|what are you|thanks|thank you|"
    r"bye|goodbye"
    r")[\s!?.]*$",
    re.IGNORECASE,
)

# Identity / capability / mandate questions — answered from the agent's grounded
# skill, so they pass the gate instead of abstaining. Searched anywhere.
_CAPABILITY_RE = re.compile(
    r"\bwhat(?:'?s| is| are)? your (?:task|tasks|role|mandate|job|purpose|"
    r"responsibilit\w+|function|capabilit\w+)\b",
    re.IGNORECASE,
)

_CONVERSATIONAL_MAX_WORDS = 12


def _is_conversational(query: str) -> bool:
    """Return True for greetings/capability/mandate questions that need no sources."""
    q = query.strip()
    if _CAPABILITY_RE.search(q):
        return True
    if len(q.split()) > _CONVERSATIONAL_MAX_WORDS:
        return False
    return bool(_CONVERSATIONAL_RE.match(q))


def _has_grounded_source(sources: list[dict], min_relevance: float) -> bool:
    """Return True if at least one retrieved source meets the relevance bar."""
    for s in sources:
        score = float(s.get("relevance_score") or s.get("score") or 0.0)
        if score >= min_relevance:
            return True
    return False


async def grounding_gate(state: dict) -> dict:
    """Evaluate grounding; set is_grounded + (if ungrounded) canned answer.

    Returns a partial state update — only the keys this node owns.
    """
    query: str = state.get("query", "")
    sources: list[dict] = state.get("sources") or []
    attached: str = state.get("attached_files_text") or ""

    if _is_conversational(query):
        logger.info("grounding_gate_pass", reason="conversational")
        return {"is_grounded": True}

    grounded = _has_grounded_source(sources, _MIN_RELEVANCE) or bool(attached.strip())

    if grounded:
        logger.info(
            "grounding_gate_pass",
            reason="sources_or_attachments",
            source_count=len(sources),
            has_attachments=bool(attached.strip()),
        )
        return {"is_grounded": True}

    logger.warning(
        "grounding_gate_blocked",
        query_preview=query[:80],
        source_count=len(sources),
    )
    return {
        "is_grounded": False,
        "answer": _ABSTENTION_ANSWER,
        "confidence": "Low",
    }
