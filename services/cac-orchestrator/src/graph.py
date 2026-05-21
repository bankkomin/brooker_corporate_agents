"""LangGraph StateGraph assembly for CAC Orchestrator."""
from __future__ import annotations

from functools import partial
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from .agents.cac import CacAgent
try:
    from services.shared.load_memory import load_memory_node
except ImportError:
    load_memory_node = None

try:
    from services.shared.daily_log import log_interaction_node
except ImportError:
    log_interaction_node = None

from .nodes.classify_intent import classify_intent
from .nodes.escalation_check import escalation_check
from .nodes.excel_navigator import excel_navigator
from .nodes.grounding_gate import grounding_gate
from .nodes.notify_escalation import notify_escalation
from .nodes.paperclip_ticket import create_paperclip_ticket
from .nodes.retrieve_context import retrieve_context
from .nodes.staging_writer import staging_writer
from .nodes.synthesise import synthesise_response
from .nodes.validate_proposal import validate_proposal
from .state import AgentState

logger = structlog.get_logger("cac-orchestrator.graph")


async def _general_handler(state: dict) -> dict:
    """Handle general/unclassified queries (no specialist needed)."""
    return {
        "agent_response": "This is a general query. Answering based on retrieved context.",
        "agent_name": "general",
        "proposed_value": None,
        "proposed_cell": None,
        "proposed_tab": None,
        "confidence_score": 0.5,
    }


def _make_should_validate(threshold: float):
    """Create a routing function that uses the configured confidence threshold."""

    def _should_validate(state: dict) -> str:
        """Route: if confidence >= threshold, validate; otherwise skip to synthesise."""
        score = state.get("confidence_score", 0.0)
        if score >= threshold and state.get("proposed_value"):
            return "validate_proposal"
        return "synthesise"

    return _should_validate


def _validation_result(state: dict) -> str:
    """Route: if validation passed, create paperclip ticket then write staging;
    otherwise skip to synthesise."""
    if state.get("validation_passed", False):
        return "paperclip_ticket"
    return "synthesise"


def build_graph(
    llm_client: Any,
    rag_client: Any,
    db_client: Any,
    skills_loader: Any = None,
    embed_fn: Any = None,
    config: Any = None,
    checkpointer: Any = None,
) -> Any:
    """Build and return the compiled CAC orchestrator graph.

    Args:
        llm_client: LLMClient instance for vLLM calls
        rag_client: RAGClient instance for Qdrant search
        db_client: DBClient instance for Postgres logging
        skills_loader: SkillsLoader instance for SKILL.md injection
        embed_fn: Optional async embedding function
        config: OrchestratorSettings instance
        checkpointer: Optional LangGraph checkpointer for state persistence

    Returns:
        Compiled LangGraph StateGraph ready for ainvoke().
    """
    from .config import settings as default_config

    cfg = config or default_config

    # Single consolidated CAC agent (doc-faithful — retreat §2.8 defines ONE
    # committee with one mandate, not specialist sub-agents). The graph below is
    # generic over `agents`, so a one-entry dict collapses the former fan-out.
    agents: dict[str, Any] = {}
    if llm_client is not None and skills_loader is not None:
        agents = {"cac": CacAgent(llm_client, skills_loader)}

    def _route_to_agent(state: dict) -> str:
        """Single-agent routing: grounded substantive turns go to the CAC agent."""
        if "cac" in agents:
            return "cac_agent"
        return "general_handler"

    graph = StateGraph(AgentState)

    # --- Add nodes ---

    # Phase 2: load_memory as first node (if shared library available)
    if load_memory_node is not None:
        graph.add_node("load_memory", load_memory_node)

    graph.add_node("classify_intent", partial(classify_intent, llm_client=llm_client))
    graph.add_node(
        "retrieve_context",
        partial(
            retrieve_context,
            rag_client=rag_client,
            embed_fn=embed_fn,
            top_k=cfg.rag_top_k,
            min_relevance=cfg.rag_min_relevance,
        ),
    )
    graph.add_node("grounding_gate", grounding_gate)

    # Specialist agents
    for name, agent in agents.items():
        graph.add_node(f"{name}_agent", agent.run)
    graph.add_node("general_handler", _general_handler)

    # Post-agent pipeline
    graph.add_node(
        "escalation_check",
        partial(escalation_check, rules_path=cfg.escalation_rules_path),
    )
    graph.add_node(
        "notify_escalation",
        partial(notify_escalation, email_notifier_url=cfg.email_notifier_url),
    )
    graph.add_node(
        "excel_navigator",
        partial(excel_navigator, schema_path=cfg.excel_schema_path),
    )
    graph.add_node(
        "validate_proposal",
        partial(validate_proposal, llm_client=llm_client, db_client=db_client),
    )
    graph.add_node(
        "staging_writer",
        partial(
            staging_writer,
            db_client=db_client,
            staging_path=cfg.staging_path,
            confidence_threshold=cfg.confidence_threshold,
        ),
    )
    graph.add_node("synthesise",
                   partial(synthesise_response,
                            llm_client=llm_client, db_client=db_client))

    # Phase 2: log_interaction as last node before END (if shared library available)
    if log_interaction_node is not None:
        graph.add_node("log_interaction", log_interaction_node)

    graph.add_node(
        "paperclip_ticket",
        partial(
            create_paperclip_ticket,
            paperclip_url=cfg.paperclip_url,
            paperclip_api_key=cfg.paperclip_api_key,
        ),
    )

    # --- Add edges ---
    if load_memory_node is not None:
        graph.set_entry_point("load_memory")
        graph.add_edge("load_memory", "classify_intent")
    else:
        graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "retrieve_context")
    graph.add_edge("retrieve_context", "grounding_gate")

    # Conditional: if the gate blocked (no grounding), skip agents and go straight
    # to synthesise so the canned abstention answer is returned through the normal
    # output path without any LLM call.
    # Build the agent-routing map dynamically so it only references nodes that were
    # actually registered above (when llm_client/skills_loader is None the agents
    # dict is empty).
    _agent_edge_map: dict[str, str] = {
        f"{name}_agent": f"{name}_agent" for name in agents
    }
    _agent_edge_map["general_handler"] = "general_handler"
    _agent_edge_map["synthesise"] = "synthesise"

    def _gate_then_route(state: dict) -> str:
        """After grounding_gate: blocked turns go to synthesise; others to agent."""
        if not state.get("is_grounded", True):
            return "synthesise"
        return _route_to_agent(state)

    graph.add_conditional_edges(
        "grounding_gate",
        _gate_then_route,
        _agent_edge_map,
    )

    # All agents converge to escalation_check
    for name in agents:
        graph.add_edge(f"{name}_agent", "escalation_check")
    graph.add_edge("general_handler", "escalation_check")

    # Sequential post-agent pipeline
    graph.add_edge("escalation_check", "notify_escalation")
    graph.add_edge("notify_escalation", "excel_navigator")

    # Conditional: validate if confident enough
    graph.add_conditional_edges(
        "excel_navigator",
        _make_should_validate(cfg.confidence_threshold),
        {
            "validate_proposal": "validate_proposal",
            "synthesise": "synthesise",
        },
    )

    # Conditional: if validation passed, create ticket then write staging;
    # otherwise skip straight to synthesise.
    # paperclip_ticket runs BEFORE staging_writer so the ticket ID is present
    # in state when the manifest is written.
    graph.add_conditional_edges(
        "validate_proposal",
        _validation_result,
        {
            "paperclip_ticket": "paperclip_ticket",
            "synthesise": "synthesise",
        },
    )

    graph.add_edge("paperclip_ticket", "staging_writer")
    graph.add_edge("staging_writer", "synthesise")

    if log_interaction_node is not None:
        graph.add_edge("synthesise", "log_interaction")
        graph.add_edge("log_interaction", END)
    else:
        graph.add_edge("synthesise", END)

    return graph.compile(checkpointer=checkpointer)
