"""FastAPI application for HR Orchestrator.

HR is a READ-ONLY department: queries return answers with citations,
no staging proposals or Excel changes.
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException

from .config import settings
from .graph import build_graph
from .models import QueryRequest, QueryResponse, Source
from .skills.loader import SkillsLoader
from .tools.db_client import DBClient
from .tools.llm_client import LLMClient
from .tools.rag_client import RAGClient

logging.basicConfig(level=settings.log_level.upper())
logger = structlog.get_logger("hr-orchestrator")

_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources on startup."""
    logger.info("hr_orchestrator_starting")

    llm_client = LLMClient(
        base_url=settings.vllm_large_url,
        model=settings.vllm_large_model,
        api_key=settings.llm_api_key,
    )
    rag_client = RAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_rest_port,
    )

    # HTTP embedder: calls rag-ingestion's /embed (Gemini under the hood today).
    _embed_http = httpx.AsyncClient(timeout=15.0)
    _embed_url = (
        os.getenv("RAG_INGESTION_URL", "http://rag-ingestion:3004").rstrip("/")
        + "/embed"
    )

    async def embed_fn(text: str) -> list[float]:
        r = await _embed_http.post(_embed_url, json={"text": text})
        r.raise_for_status()
        return r.json()["vector"]

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
        embed_fn=embed_fn,
    )

    _state["llm_client"] = llm_client
    _state["rag_client"] = rag_client
    _state["db_client"] = db_client
    _state["db_pool"] = db_pool
    _state["graph"] = compiled_graph
    _state["checkpointer"] = checkpointer
    _state["checkpointer_cm"] = checkpointer_cm

    logger.info("hr_orchestrator_ready")
    yield

    # Shutdown
    await llm_client.close()
    await rag_client.close()
    if checkpointer_cm is not None:
        await checkpointer_cm.__aexit__(None, None, None)
    if db_pool is not None:
        await db_pool.close()
    logger.info("hr_orchestrator_stopped")


app = FastAPI(
    title="hr-orchestrator",
    version="1.0.0",
    description="HR Department AI Agent Orchestrator (read-only)",
    lifespan=lifespan,
)


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Process an HR query through the agent graph."""
    graph = _state.get("graph")
    db_client: DBClient | None = _state.get("db_client")
    if graph is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    start = time.monotonic()

    # Build initial state -- no staging/Excel fields (HR is read-only)
    initial_state = {
        "query": req.query,
        "user_id": req.user_id,
        "channel": req.channel,
        "thread_ts": req.thread_ts,
        "messages": [],
        # Phase 2 shared fields
        "agent_memory": "",
        "vault_root": settings.vault_root,
        "agent_id": "hr-orchestrator",
        "dept_id": "hr",
        # Classification
        "intent": "",
        "intent_confidence": 0.0,
        # Retrieval
        "sources": [],
        "context_text": "",
        # Agent
        "agent_response": "",
        "agent_name": "",
        "confidence_score": 0.0,
        # Escalation
        "escalation_triggered": False,
        "escalation_detail": None,
        # Synthesis
        "answer": "",
        "confidence": "Low",
        "response": "",
        # Metadata
        "processing_start": start,
        "paperclip_ticket_id": None,
        "interaction_id": None,
        # Daily log fields
        "citations": [],
        "proposal_id": None,
    }

    # Create interaction before graph
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

    # Run graph
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

    # Update interaction with results
    if db_client and interaction_id:
        try:
            await db_client.update_interaction(
                interaction_id=interaction_id,
                intent=result.get("intent"),
                response=result.get("answer", ""),
                sources_count=len(sources),
                escalation=result.get("escalation_triggered", False),
                confidence=result.get("confidence_score"),
                processing_ms=processing_ms,
                paperclip_ticket_id=result.get("paperclip_ticket_id"),
            )
        except Exception as exc:
            logger.error("update_interaction_failed", error=str(exc))

    return QueryResponse(
        answer=result.get("answer", ""),
        sources=sources,
        escalation_triggered=result.get("escalation_triggered", False),
        confidence=result.get("confidence", "Low"),
        processing_time_ms=processing_ms,
    )


@app.get("/health")
async def health() -> dict:
    """Service health check."""
    return {"status": "healthy", "service": "hr-orchestrator"}


@app.get("/heartbeat")
async def heartbeat() -> dict:
    """Paperclip heartbeat endpoint."""
    return {"status": "ok"}
