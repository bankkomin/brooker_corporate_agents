"""LangGraph AgentState definition for hr-orchestrator.

HR is a READ-ONLY department: no staging proposals, no Excel writes.
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class HRAgentState(TypedDict):
    """Shared state threaded through every node in the HR LangGraph pipeline."""

    # Input
    query: str
    user_id: str
    channel: str
    thread_ts: str | None
    messages: Annotated[list[BaseMessage], add_messages]

    # Phase 2 shared library fields
    agent_memory: str
    vault_root: str
    agent_id: str
    dept_id: str

    # classify_intent output
    intent: str
    intent_confidence: float

    # retrieve_context output
    sources: list[dict]
    context_text: str

    # Portal-attached files (pre-loaded by main.py before the graph runs).
    attached_files_text: str

    # grounding_gate output — True means the turn has adequate source grounding
    # (or is conversational) and should proceed normally; False triggers abstention.
    is_grounded: bool
    # True when grounding_gate passed because the query is conversational /
    # capability (greeting, "what is your mandate?"). synthesise reads this to
    # SKIP the post-LLM citation-grounding backstop — capability answers come
    # from the SKILL mandate, not retrieved sources, so the backstop has nothing
    # legitimate to verify against and would wrongly replace the answer.
    is_capability_bypass: bool

    # agent output
    agent_response: str
    agent_name: str
    confidence_score: float

    # escalation_check output
    escalation_triggered: bool
    escalation_detail: str | None

    # synthesise output
    answer: str
    confidence: str
    response: str  # alias used by daily_log node

    # metadata
    processing_start: float
    paperclip_ticket_id: str | None
    interaction_id: int | None

    # daily log fields (used by shared log_interaction_node)
    citations: list[str]
    proposal_id: str | None
