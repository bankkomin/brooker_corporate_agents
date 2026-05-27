"""Grounding gate — hard-blocks ungrounded substantive answers.

Why this node exists
--------------------
The synthesise node has a system-prompt instruction telling the LLM not to
fabricate when there are no sources. That is probabilistic: the model *usually*
abstains but can still hallucinate a confident answer. This gate makes
abstention deterministic by never invoking specialist agents or the LLM
synthesiser when there is nothing to ground an answer on.

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

logger = structlog.get_logger("cac-orchestrator.grounding_gate")

# Minimum relevance score to consider a source grounded.
# Mirrors the default in retrieve_context; overridden by env RAG_MIN_RELEVANCE.
_DEFAULT_MIN_RELEVANCE: float = 0.50
_MIN_RELEVANCE: float = float(os.getenv("RAG_MIN_RELEVANCE", str(_DEFAULT_MIN_RELEVANCE)))

_URL_RE = re.compile(r"https?://\S+")
_SHAREPOINT_RE = re.compile(r"sharepoint\.com|1drv\.ms|onedrive", re.I)

# Generic fallback only (used if abstain() builder errors out).
_ABSTENTION_ANSWER = (
    "I don't have reference material on this topic in my knowledge base yet. "
    "Please share a relevant document or data source and I'll analyse it."
)


def abstain(query: str) -> str:
    """Context-aware abstain for the CAC chat path.

    Does not contradict the user when they JUST shared a link, names what the
    CAC agent is actually grounded in, and routes Data-Pack-style SharePoint
    links to the report path that can actually open them.
    """
    q = query or ""
    has_url = bool(_URL_RE.search(q))
    is_share = bool(_SHAREPOINT_RE.search(q))
    base = ("I don't have an answer for that in the CAC agent's ingested records "
            "(cac_docs, cac_knowledge, cross-reads from finance/risk/cio/ceo).")
    if is_share:
        return (f"{base} I can see the SharePoint/OneDrive link you shared, but the "
                f"chat path can't open external files. To turn this Data Pack into "
                f"the CAC Meeting Report .docx, rephrase as \"produce CAC report "
                f"from this link\" — the report pipeline reads the workbook directly.")
    if has_url:
        return (f"{base} The link in your message isn't a source I can fetch from "
                f"this chat path — upload the file directly to this channel and "
                f"I'll ingest it.")
    return (f"{base} Share the relevant document (PDF / Word / Excel) directly in "
            f"this channel and I'll ingest and analyse it.")

# Patterns that identify conversational / meta queries that should always reply.
# Checked against the lowercased, stripped query.
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

# Identity / capability / mandate questions ("what is your task?", "what's your
# mandate?"). These are answered from the agent's own grounded skill, so they
# pass the gate instead of abstaining. Searched anywhere in the query.
_CAPABILITY_RE = re.compile(
    r"\bwhat(?:'?s| is| are)? your (?:task|tasks|role|mandate|job|purpose|"
    r"responsibilit\w+|function|capabilit\w+)\b",
    re.IGNORECASE,
)

# Hard length cap: queries above this word count cannot be conversational.
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
        # Mark this turn so synthesise knows the answer comes from the SKILL
        # mandate (not retrieved sources). Without this, the post-LLM citation
        # backstop verifies the LLM's [N] markers against retrieval noise and
        # wrongly replaces legitimate capability/greeting answers with abstain.
        return {"is_grounded": True, "is_capability_bypass": True}

    # SharePoint/OneDrive link in the query: the chat path can NOT open it
    # (only the cac-report pipeline calls MS Graph). Short-circuit even if RAG
    # found weakly-related chunks — otherwise the synthesiser produces a
    # confidently-cited but irrelevant answer that pretends to read the file.
    if _SHAREPOINT_RE.search(query or ""):
        logger.warning("grounding_gate_blocked", reason="external_share_link",
                       query_preview=query[:80])
        return {
            "is_grounded": False,
            "answer": abstain(query),
            "confidence": "Low",
            "proposed_value": None,
            "proposed_cell": None,
            "proposed_tab": None,
            "staging_proposal_id": None,
        }

    grounded = _has_grounded_source(sources, _MIN_RELEVANCE) or bool(attached.strip())

    if grounded:
        logger.info(
            "grounding_gate_pass",
            reason="sources_or_attachments",
            source_count=len(sources),
            has_attachments=bool(attached.strip()),
        )
        return {"is_grounded": True}

    # Ungrounded substantive query — short-circuit.
    logger.warning(
        "grounding_gate_blocked",
        query_preview=query[:80],
        source_count=len(sources),
    )
    return {
        "is_grounded": False,
        # Pre-populate answer so synthesise's LLM call is skipped (see synthesise.py).
        "answer": abstain(query),
        "confidence": "Low",
        # Ensure no proposal bleed-through from a previous turn in the thread.
        "proposed_value": None,
        "proposed_cell": None,
        "proposed_tab": None,
        "staging_proposal_id": None,
    }
