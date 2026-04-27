"""LangGraph StateGraph assembly for CAC Orchestrator."""
from __future__ import annotations

from functools import partial
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from .agents.alm import AlmAgent
from .agents.capital import CapitalAgent
from .agents.cfo import CFOAgent
from .agents.funding import FundingAgent
from .agents.liquidity import LiquidityAgent
from .nodes.classify_intent import classify_intent
from .nodes.escalation_check import escalation_check
from .nodes.excel_navigator import excel_navigator
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

    # Build agent instances with DI (requires llm_client + skills_loader)
    agents: dict[str, Any] = {}
    if llm_client is not None and skills_loader is not None:
        agents = {
            "liquidity": LiquidityAgent(llm_client, skills_loader),
            "capital": CapitalAgent(llm_client, skills_loader),
            "alm": AlmAgent(llm_client, skills_loader),
            "funding": FundingAgent(llm_client, skills_loader),
            # CFO is a cross-domain synthesiser; routed by classify_intent
            # when the query requires a whole-of-firm view.
            "cfo": CFOAgent(llm_client, skills_loader),
        }

    def _route_to_agent(state: dict) -> str:
        """Route to specialist agent based on classified intent."""
        intent = state.get("intent", "general")
        if intent in agents:
            return f"{intent}_agent"
        return "general_handler"

    graph = StateGraph(AgentState)

    # --- Add nodes ---
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
    graph.add_node("synthesise", partial(synthesise_response, llm_client=llm_client))
    graph.add_node(
        "paperclip_ticket",
        partial(
            create_paperclip_ticket,
            paperclip_url=cfg.paperclip_url,
            paperclip_api_key=cfg.paperclip_api_key,
        ),
    )

    # --- Add edges ---
    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "retrieve_context")

    # Conditional: route to correct agent.
    # Build the map dynamically so it only references nodes that were actually
    # registered above.  When llm_client/skills_loader is None the agents dict
    # is empty and none of the specialist node names exist in the graph.
    _agent_edge_map: dict[str, str] = {
        f"{name}_agent": f"{name}_agent" for name in agents
    }
    _agent_edge_map["general_handler"] = "general_handler"

    graph.add_conditional_edges(
        "retrieve_context",
        _route_to_agent,
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
    graph.add_edge("synthesise", END)

    return graph.compile(checkpointer=checkpointer)
