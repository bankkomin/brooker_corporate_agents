"""FastAPI application for CAC Orchestrator."""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException

try:
    from prometheus_client import make_asgi_app as make_metrics_app

    from services.shared.metrics_middleware import PrometheusMiddleware
except ImportError:
    PrometheusMiddleware = None
    make_metrics_app = None

from .config import settings
from .graph import build_graph
from .models import QueryRequest, QueryResponse, Source
from .skills.loader import SkillsLoader
from .tools.db_client import DBClient
from .tools.llm_client import LLMClient
from .tools.rag_client import RAGClient

logging.basicConfig(level=settings.log_level.upper())
logger = structlog.get_logger("cac-orchestrator")

_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources on startup."""
    logger.info("cac_orchestrator_starting")

    llm_client = LLMClient(
        base_url=settings.vllm_large_url,
        model=settings.vllm_large_model,
        api_key=settings.llm_api_key,
    )
    rag_client = RAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_rest_port,
    )

    # DB pool -- graceful degradation if Postgres unavailable
    db_pool = None
    try:
        import asyncpg

        db_pool = await asyncpg.create_pool(
            settings.postgres_dsn,
            min_size=2,
            max_size=10,
        )
    except Exception as exc:
        logger.warning("postgres_pool_failed", error=str(exc))

    db_client = DBClient(pool=db_pool)

    # Skills loader for agent SKILL.md injection
    skills_loader = SkillsLoader(skills_dir=settings.skills_path)

    # LangGraph checkpointer -- graceful degradation if Postgres unavailable
    checkpointer = None
    checkpointer_cm = None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.postgres_dsn)
        checkpointer = await checkpointer_cm.__aenter__()
        await checkpointer.setup()
        logger.info("checkpointer_ready")
    except Exception as exc:
        logger.warning("checkpointer_setup_failed", error=str(exc))
        checkpointer = None
        checkpointer_cm = None

    compiled_graph = build_graph(
        llm_client=llm_client,
        rag_client=rag_client,
        db_client=db_client,
        skills_loader=skills_loader,
        checkpointer=checkpointer,
    )

    _state["llm_client"] = llm_client
    _state["rag_client"] = rag_client
    _state["db_client"] = db_client
    _state["db_pool"] = db_pool
    _state["graph"] = compiled_graph
    _state["checkpointer"] = checkpointer
    _state["checkpointer_cm"] = checkpointer_cm

    logger.info("cac_orchestrator_ready")
    yield

    # Shutdown
    await llm_client.close()
    await rag_client.close()
    if checkpointer_cm is not None:
        await checkpointer_cm.__aexit__(None, None, None)
    if db_pool is not None:
        await db_pool.close()
    logger.info("cac_orchestrator_stopped")


app = FastAPI(
    title="cac-orchestrator",
    version="1.0.0",
    description="CAC Committee AI Agent Orchestrator",
    lifespan=lifespan,
)

if PrometheusMiddleware is not None:
    app.add_middleware(PrometheusMiddleware)

if make_metrics_app is not None:
    metrics_app = make_metrics_app()
    app.mount("/metrics", metrics_app)


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Process a committee query through the agent graph."""
    graph = _state.get("graph")
    db_client: DBClient | None = _state.get("db_client")
    if graph is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    start = time.monotonic()

    # Build initial state
    initial_state = {
        "query": req.query,
        "user_id": req.user_id,
        "channel": req.channel,
        "thread_ts": req.thread_ts,
        "messages": [],
        "intent": "",
        "intent_confidence": 0.0,
        "sources": [],
        "context_text": "",
        "agent_response": "",
        "agent_name": "",
        "proposed_value": None,
        "proposed_cell": None,
        "proposed_tab": None,
        "old_value": "",
        "escalation_triggered": False,
        "escalation_detail": None,
        "excel_nav": None,
        "validation_passed": False,
        "validation_warnings": [],
        "staging_proposal_id": None,
        "answer": "",
        "confidence": "Low",
        "confidence_score": 0.0,
        "processing_start": start,
        "paperclip_ticket_id": None,
        # Phase 2 shared library fields
        "agent_memory": "",
        "vault_root": settings.vault_root,
        "agent_id": "cac-orchestrator",
        "dept_id": "cac",
    }

    # Phase 1: create interaction before graph
    interaction_id = None
    if db_client:
        try:
            interaction_id = await db_client.create_interaction(
                user_id=req.user_id,
                channel=req.channel,
                thread_ts=req.thread_ts,
                query=req.query,
            )
        except Exception as exc:
            logger.error("create_interaction_failed", error=str(exc))

    initial_state["interaction_id"] = interaction_id

    # Run graph -- thread_ts provides per-thread state isolation
    config = {"configurable": {"thread_id": f"{req.user_id}:{req.thread_ts or req.channel}"}}
    try:
        result = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.error(
            "graph_execution_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {type(exc).__name__}: {exc}",
        ) from exc

    processing_ms = int((time.monotonic() - start) * 1000)

    # Build source models
    sources = [
        Source(
            type=s.get("type", "document"),
            filename=s.get("filename", ""),
            page=s.get("page"),
            date=s.get("date"),
            uploader=s.get("uploader"),
            excerpt=s.get("excerpt", ""),
            relevance_score=s.get("relevance_score", 0.0),
        )
        for s in result.get("sources", [])
    ]

    # Phase 2: update interaction with results
    if db_client and interaction_id:
        try:
            await db_client.update_interaction(
                interaction_id=interaction_id,
                intent=result.get("intent"),
                response=result.get("answer", ""),
                sources_count=len(sources),
                escalation=result.get("escalation_triggered", False),
                staging_proposal_id=result.get("staging_proposal_id"),
                confidence=result.get("confidence_score"),
                processing_ms=processing_ms,
                paperclip_ticket_id=result.get("paperclip_ticket_id"),
            )
        except Exception as exc:
            logger.error("update_interaction_failed", error=str(exc))

    return QueryResponse(
        answer=result.get("answer", ""),
        sources=sources,
        excel_nav=result.get("excel_nav"),
        staging_proposal_id=result.get("staging_proposal_id"),
        escalation_triggered=result.get("escalation_triggered", False),
        confidence=result.get("confidence", "Low"),
        processing_time_ms=processing_ms,
    )


@app.get("/health")
async def health() -> dict:
    """Service health check."""
    return {"status": "healthy", "service": "cac-orchestrator"}


@app.get("/heartbeat")
async def heartbeat() -> dict:
    """Paperclip heartbeat endpoint."""
    return {"status": "ok"}
