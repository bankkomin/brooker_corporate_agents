"""LangGraph StateGraph assembly for HR Orchestrator.

HR is a READ-ONLY department: no staging_writer, no excel_navigator,
no validate_proposal. Simplified pipeline:

  load_memory -> classify_intent -> retrieve_context -> [specialist routing]
  -> escalation_check -> synthesise -> log_interaction -> END
"""
from __future__ import annotations

from functools import partial
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from .agents.compensation import CompensationAgent
from .agents.compliance import ComplianceAgent
from .agents.general import GeneralHRAgent
from .agents.recruitment import RecruitmentAgent

# Phase 2 shared library: load_memory (FIRST node)
try:
    from services.shared.load_memory import load_memory_node
except ImportError:
    load_memory_node = None

# Phase 2 shared library: log_interaction (LAST node before END)
try:
    from services.shared.daily_log import log_interaction_node
except ImportError:
    log_interaction_node = None

from .nodes.classify_intent import classify_intent
from .nodes.escalation_check import escalation_check
from .nodes.paperclip_ticket import create_paperclip_ticket
from .nodes.retrieve_context import retrieve_context
from .nodes.synthesise import synthesise_response
from .state import HRAgentState

logger = structlog.get_logger("hr-orchestrator.graph")


async def _general_handler(state: dict) -> dict:
    """Handle general/unclassified HR queries (no specialist needed)."""
    return {
        "agent_response": "This is a general HR query. Answering based on retrieved context.",
        "agent_name": "general",
        "confidence_score": 0.5,
    }


def build_graph(
    llm_client: Any,
    rag_client: Any,
    db_client: Any,
    skills_loader: Any = None,
    embed_fn: Any = None,
    config: Any = None,
    checkpointer: Any = None,
) -> Any:
    """Build and return the compiled HR orchestrator graph.

    Args:
        llm_client: LLMClient instance for LLM calls
        rag_client: RAGClient instance for Qdrant search
        db_client: DBClient instance for Postgres logging
        skills_loader: SkillsLoader instance for SKILL.md injection
        embed_fn: Optional async embedding function
        config: HROrchestratorSettings instance
        checkpointer: Optional LangGraph checkpointer for state persistence

    Returns:
        Compiled LangGraph StateGraph ready for ainvoke().
    """
    from .config import settings as default_config

    cfg = config or default_config

    # Build agent instances with DI
    agents: dict[str, Any] = {}
    if llm_client is not None and skills_loader is not None:
        agents = {
            "recruitment": RecruitmentAgent(llm_client, skills_loader),
            "compensation": CompensationAgent(llm_client, skills_loader),
            "compliance": ComplianceAgent(llm_client, skills_loader),
            "general": GeneralHRAgent(llm_client, skills_loader),
        }

    def _route_to_agent(state: dict) -> str:
        """Route to specialist agent based on classified intent."""
        intent = state.get("intent", "general")
        if intent in agents:
            return f"{intent}_agent"
        return "general_handler"

    graph = StateGraph(HRAgentState)

    # --- Add nodes ---

    # Phase 2: load_memory as FIRST node (if shared library available)
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

    # Specialist agents
    for name, agent in agents.items():
        graph.add_node(f"{name}_agent", agent.run)
    graph.add_node("general_handler", _general_handler)

    # Post-agent pipeline (simplified: no excel_navigator, no staging)
    graph.add_node(
        "escalation_check",
        partial(escalation_check, rules_path=cfg.escalation_rules_path),
    )

    # Resolve db_conn for synthesise (knowledge gap tracking)
    _db_conn = getattr(db_client, "pool", None) if db_client else None
    graph.add_node(
        "synthesise",
        partial(synthesise_response, llm_client=llm_client, db_conn=_db_conn),
    )

    graph.add_node(
        "paperclip_ticket",
        partial(
            create_paperclip_ticket,
            paperclip_url=cfg.paperclip_url,
            paperclip_api_key=cfg.paperclip_api_key,
        ),
    )

    # Phase 2: log_interaction as LAST node before END (if shared library available)
    if log_interaction_node is not None:
        graph.add_node("log_interaction", log_interaction_node)

    # --- Add edges ---

    # Entry point: load_memory -> classify_intent (or classify_intent directly)
    if load_memory_node is not None:
        graph.set_entry_point("load_memory")
        graph.add_edge("load_memory", "classify_intent")
    else:
        graph.set_entry_point("classify_intent")

    graph.add_edge("classify_intent", "retrieve_context")

    # Conditional: route to correct HR agent
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

    # escalation_check -> synthesise -> paperclip_ticket -> (log_interaction ->) END
    graph.add_edge("escalation_check", "synthesise")
    graph.add_edge("synthesise", "paperclip_ticket")

    if log_interaction_node is not None:
        graph.add_edge("paperclip_ticket", "log_interaction")
        graph.add_edge("log_interaction", END)
    else:
        graph.add_edge("paperclip_ticket", END)

    return graph.compile(checkpointer=checkpointer)
