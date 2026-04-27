"""LangGraph AgentState definition for cac-orchestrator."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state threaded through every node in the LangGraph pipeline."""

    # Input
    query: str
    user_id: str
    channel: str
    thread_ts: str | None
    messages: Annotated[list[BaseMessage], add_messages]

    # classify_intent output
    intent: str
    intent_confidence: float

    # retrieve_context output
    sources: list[dict]
    context_text: str

    # agent output
    agent_response: str
    agent_name: str
    proposed_value: str | None
    proposed_cell: str | None
    old_value: str

    # escalation_check output
    escalation_triggered: bool
    escalation_detail: str | None

    # excel_navigator output
    excel_nav: str | None

    # validate_proposal output
    validation_passed: bool
    validation_warnings: list[str]

    # staging_writer output
    staging_proposal_id: str | None

    # synthesise output
    answer: str
    confidence: str
    confidence_score: float

    # metadata
    processing_start: float
    paperclip_ticket_id: str | None

    # Stage 5 additions
    interaction_id: int | None
    proposed_tab: str | None
