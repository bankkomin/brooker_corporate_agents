"""FastAPI application for CAC Orchestrator."""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException

try:
    from services.shared.metrics_middleware import PrometheusMiddleware
    from prometheus_client import make_asgi_app as make_metrics_app
except ImportError:
    PrometheusMiddleware = None
    make_metrics_app = None

from .config import settings
from .graph import build_graph
from .models import QueryRequest, QueryResponse, Source
from .skills.loader import SkillsLoader
from .tools.db_client import DBClient
from .tools.llm_client import LLMClient
from .tools.portal_files import fetch_and_extract
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

    # HTTP embedder: calls rag-ingestion's /embed (Gemini under the hood today).
    import httpx as _httpx
    _embed_http = _httpx.AsyncClient(timeout=15.0)
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
    _state["embed_fn"] = embed_fn
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


_SUMMARY_SYSTEM = (
    "You are a corporate committee AI assistant for the Capital Allocation & "
    "ALCO Committee. Produce a concise EXECUTIVE BRIEF (max 200 words) in "
    "markdown. Use this structure:\n"
    "**Answer:** 1-2 sentences directly answering the question.\n"
    "**Key facts:** 3-5 bullets with cited numbers / dates / sources [filename].\n"
    "**Risks / caveats:** 1-3 bullets (omit if none apply).\n"
    "Cite source filenames inline like [filename.pdf]. Never invent figures. "
    "If retrieved context is empty, say so explicitly and ask the user to share "
    "a relevant document. No greeting, no preamble."
)


@app.post("/summary")
async def summary(req: QueryRequest) -> dict:
    """Concise executive brief endpoint. Same retrieval as /query but a single
    LLM call with a summary-mode prompt — returns markdown, no agent path,
    no escalation, no staging proposal. Useful for quick committee briefings."""
    graph_components = _state
    llm_client = graph_components.get("llm_client")
    rag_client = graph_components.get("rag_client")
    if llm_client is None or rag_client is None:
        raise HTTPException(503, "orchestrator components not ready")

    # Use the graph's retrieve_context helper directly.
    from .nodes.retrieve_context import retrieve_context
    import httpx as _httpx, os as _os
    _embed_url = (_os.getenv("RAG_INGESTION_URL", "http://rag-ingestion:3004").rstrip("/") + "/embed")
    async def _embed(text: str) -> list[float]:
        async with _httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(_embed_url, json={"text": text})
            r.raise_for_status()
            return r.json()["vector"]

    state = {"query": req.query, "dept_id": req.dept_id or settings.dept_id}
    retrieved = await retrieve_context(state, rag_client=rag_client, embed_fn=_embed,
                                        top_k=settings.rag_top_k,
                                        min_relevance=settings.rag_min_relevance)
    sources = retrieved.get("sources", [])
    context_text = retrieved.get("context_text", "")

    user_msg = (
        f"Question: {req.query}\n\n"
        f"Retrieved context:\n{context_text or '(no relevant context retrieved)'}"
    )
    answer = await llm_client.chat(
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return {
        "answer": answer,
        "confidence": "Medium",
        "sources": [
            {"filename": s.get("filename", ""), "excerpt": s.get("excerpt", "")[:200],
             "relevance_score": s.get("relevance_score", 0.0)}
            for s in sources
        ],
    }


@app.get("/proposals/pending")
async def list_pending_proposals() -> dict:
    """List the JSON manifests sitting in /data/staging/pending/."""
    from pathlib import Path as _Path
    staging = _Path(settings.staging_path) / "pending"
    items: list[dict] = []
    if staging.is_dir():
        import json as _json
        for f in sorted(staging.glob("*.json"))[:50]:
            try:
                m = _json.loads(f.read_text(encoding="utf-8"))
                items.append({
                    "id": m.get("id") or f.stem,
                    "agent": m.get("agent"),
                    "file": m.get("file"),
                    "tab": m.get("tab"),
                    "cell": m.get("cell"),
                    "old_value": m.get("old_value"),
                    "new_value": m.get("new_value"),
                    "confidence": m.get("confidence"),
                    "reasoning": (m.get("reasoning") or "")[:200],
                    "status": m.get("status", "pending"),
                    "source": m.get("source"),
                    "filename": f.name,
                })
            except Exception:
                continue
    return {"count": len(items), "proposals": items}


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Process a committee query through the agent graph."""
    graph = _state.get("graph")
    db_client: DBClient | None = _state.get("db_client")
    if graph is None:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    start = time.monotonic()

    # Pull any portal-attached files and pre-load their contents into context
    # before the graph runs. Failures are logged but never block the query.
    attached_context = await fetch_and_extract(
        files=req.files,
        portal_base_url=req.portal_base_url,
        auth_token=req.auth_token,
    )

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
        "attached_files_text": attached_context,
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
        "agent_id": settings.agent_id,
        # Honour the dept_id the gateway forwards so a single orchestrator
        # binary can serve multiple departments without a redeploy.
        "dept_id": req.dept_id or settings.dept_id,
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


@app.get("/report/monthly-cfo")
async def monthly_cfo_report() -> dict:
    """Generate the monthly CAC report for the CFO.

    Queries cac_docs + cac_knowledge for the current month's balance-sheet,
    liquidity, funding, and ALM data, then asks the LLM to produce a
    structured executive brief using the CAC monthly CFO report template.

    Returns:
        {"report": "<markdown>", "month": "May 2026", "sources": [...]}
    """
    from datetime import date

    graph_components = _state
    llm_client = graph_components.get("llm_client")
    rag_client = graph_components.get("rag_client")
    embed_fn = graph_components.get("embed_fn")
    if llm_client is None or rag_client is None:
        raise HTTPException(503, "orchestrator components not ready")

    today = date.today()
    month_label = today.strftime("%B %Y")   # e.g. "May 2026"
    period_ym = today.strftime("%Y-%m")     # e.g. "2026-05"

    # Build a rich retrieval query that covers all four pillars
    retrieval_query = (
        f"CAC monthly report {period_ym}: balance sheet assets liabilities "
        "capital allocation liquidity runway funding covenants ALM duration gap "
        "limit breaches recommendations CFO"
    )

    from .nodes.retrieve_context import retrieve_context
    import httpx as _httpx
    import os as _os

    _embed_url = (
        _os.getenv("RAG_INGESTION_URL", "http://rag-ingestion:3004").rstrip("/")
        + "/embed"
    )

    async def _embed(text: str) -> list[float]:
        async with _httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(_embed_url, json={"text": text})
            r.raise_for_status()
            return r.json()["vector"]

    _embed_fn = embed_fn if embed_fn is not None else _embed

    state = {"query": retrieval_query, "dept_id": settings.dept_id}
    retrieved = await retrieve_context(
        state,
        rag_client=rag_client,
        embed_fn=_embed_fn,
        top_k=12,
        min_relevance=0.60,
    )
    sources = retrieved.get("sources", [])
    context_text = retrieved.get("context_text", "")

    system_prompt = (
        "You are the Capital Allocation & ALCO Committee AI. "
        "Produce the monthly CAC report to the CFO (Supane) in markdown. "
        "Follow this exact structure — fill every section from the retrieved context. "
        "If a figure is unavailable, write 'data pending'. "
        "Never invent numbers. Cite source filenames inline like [filename.pdf].\n\n"
        "## Required sections\n"
        "1. Executive Summary (3–5 sentences: overall health, biggest change, any limit breaches)\n"
        "2. Balance Sheet (total assets, liabilities, net worth, D/E ratio, MoM movement)\n"
        "3. Capital Allocation (investment-to-assets ratio vs 40% ceiling, Three-Engine targets)\n"
        "4. Liquidity — Stay Liquid (runway months, BTC sovereignty buffer, stress test)\n"
        "5. Funding & Covenants (drawn/available, leverage, cost of funds, maturities <90d)\n"
        "6. Asset-Liability Risk (duration gap, refinancing due 12m, collateral coverage)\n"
        "7. Limit Breaches & Escalations (table — Metric | Value | Limit | Action)\n"
        "8. Recommendations to CFO / IC / Board (numbered, tagged by approval level)\n\n"
        "Begin the report with:\n"
        f"# CAC Monthly Report — {month_label}\n"
        f"**To:** Supane, CFO  ·  **From:** Capital Allocation & ALCO Committee\n"
        f"**Period:** {month_label}  ·  **Prepared:** {today.isoformat()}\n"
    )

    user_msg = (
        f"Month: {month_label}\n\n"
        f"Retrieved CAC knowledge:\n{context_text or '(no relevant context retrieved — include data-pending placeholders)'}"
    )

    logger.info("monthly_cfo_report.generating", month=month_label, source_count=len(sources))

    report_text = await llm_client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.15,
        max_tokens=2000,
    )

    logger.info("monthly_cfo_report.done", month=month_label, chars=len(report_text))

    return {
        "report": report_text,
        "month": month_label,
        "period": period_ym,
        "sources": [
            {
                "filename": s.get("filename", ""),
                "excerpt": s.get("excerpt", "")[:200],
                "relevance_score": s.get("relevance_score", 0.0),
            }
            for s in sources
        ],
    }


@app.get("/health")
async def health() -> dict:
    """Service health check."""
    return {"status": "healthy", "service": "cac-orchestrator"}


@app.get("/heartbeat")
async def heartbeat() -> dict:
    """Paperclip heartbeat endpoint."""
    return {"status": "ok"}
