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

_URL_RE = re.compile(r"https?://\S+")
_SHAREPOINT_RE = re.compile(r"sharepoint\.com|1drv\.ms|onedrive", re.I)

# Generic fallback only (used if abstain() builder errors out).
_ABSTENTION_ANSWER = (
    "I don't have reference material on this topic in my knowledge base yet. "
    "Please share a relevant document or data source and I'll analyse it."
)


def abstain(query: str) -> str:
    """Context-aware abstain for the HR chat path.

    HR's ingested record is thin (two completed internal-control self-assessment
    questionnaires in Thai). The abstain names that explicitly, acknowledges any
    link the user shared (instead of asking them to share a doc they just did),
    and notes the chat path can't open external files.
    """
    q = query or ""
    has_url = bool(_URL_RE.search(q))
    is_share = bool(_SHAREPOINT_RE.search(q))
    base = ("I don't have an answer for that in the HR agent's ingested records "
            "(two internal-control self-assessment questionnaires in Thai — "
            "employment-contract storage + working-time/leave).")
    if is_share:
        return (f"{base} I can see the SharePoint/OneDrive link you shared, but the "
                f"chat path can't open external files. Upload the document directly "
                f"to this channel and I'll ingest it into the HR knowledge base.")
    if has_url:
        return (f"{base} The link in your message isn't a source I can fetch from "
                f"this chat path — upload the file directly to this channel and "
                f"I'll ingest it.")
    return (f"{base} Share the relevant document (PDF / Word / Excel) directly in "
            f"this channel and I'll ingest and analyse it.")

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
        # is_capability_bypass tells synthesise to skip the post-LLM citation
        # backstop — capability answers come from the SKILL mandate, not from
        # retrieved sources, so the backstop has nothing legit to verify against.
        return {"is_grounded": True, "is_capability_bypass": True}

    # SharePoint/OneDrive link: chat path can NOT open external files. Short-
    # circuit even if RAG returned weakly-related chunks, otherwise synthesise
    # produces a confidently-cited but irrelevant answer that pretends to read it.
    if _SHAREPOINT_RE.search(query or ""):
        logger.warning("grounding_gate_blocked", reason="external_share_link",
                       query_preview=query[:80])
        return {
            "is_grounded": False,
            "answer": abstain(query),
            "confidence": "Low",
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

    logger.warning(
        "grounding_gate_blocked",
        query_preview=query[:80],
        source_count=len(sources),
    )
    return {
        "is_grounded": False,
        "answer": abstain(query),
        "confidence": "Low",
    }
