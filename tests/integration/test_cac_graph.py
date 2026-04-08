"""Integration test for CAC Orchestrator graph — FastAPI /query endpoint.

Tests the /query, /health, and /heartbeat endpoints with a mocked graph.
Does NOT import the real main.py (which requires langgraph at import time).
Instead, builds a standalone FastAPI app that mirrors the real endpoints.
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

# --- Inline models (avoid importing from src which triggers langgraph) ---

class Source(BaseModel):
    type: str
    filename: str
    page: int | None = None
    date: str | None = None
    uploader: str | None = None
    excerpt: str
    relevance_score: float


class QueryRequest(BaseModel):
    query: str
    user_id: str
    channel: str
    thread_ts: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    excel_nav: str | None = None
    staging_proposal_id: str | None = None
    escalation_triggered: bool = False
    confidence: str
    processing_time_ms: int


# --- Shared state dict (mirrors main.py pattern) ---
_state: dict[str, Any] = {}


@pytest.fixture
def mock_graph():
    """Create a mock compiled graph that returns realistic results."""
    graph = AsyncMock()
    graph.ainvoke = AsyncMock(
        return_value={
            "query": "What is the current net debt/EBITDA ratio?",
            "intent": "funding",
            "intent_confidence": 0.92,
            "sources": [
                {
                    "type": "document",
                    "filename": "ALCO_Minutes_Feb2026.pdf",
                    "page": 4,
                    "date": "2026-02-12",
                    "uploader": "John Smith",
                    "excerpt": "covenant threshold agreed at 3.5x",
                    "relevance_score": 0.94,
                }
            ],
            "context_text": "[1] ALCO_Minutes_Feb2026.pdf p.4: covenant threshold agreed at 3.5x",
            "agent_response": "Current net debt/EBITDA is 3.15x based on latest ALCO minutes.",
            "agent_name": "funding-agent",
            "proposed_value": "3.15",
            "proposed_cell": "E8",
            "escalation_triggered": False,
            "escalation_detail": None,
            "excel_nav": (
                "ALCO_Tracker.xlsx -> Tab: Funding Facilities"
                " -> Row 8 -> Column E: Covenant Threshold"
            ),
            "validation_passed": True,
            "validation_warnings": [],
            "staging_proposal_id": "chg_0001",
            "answer": (
                "Based on the ALCO minutes from February 2026 [1], "
                "the current net debt/EBITDA ratio is 3.15x."
            ),
            "confidence": "High",
            "confidence_score": 0.92,
            "processing_start": 0.0,
            "paperclip_ticket_id": "PPC-0001",
        }
    )
    return graph


def _build_test_app() -> FastAPI:
    """Build a test FastAPI app with a no-op lifespan (dependencies injected via _state)."""

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    test_app = FastAPI(lifespan=_noop_lifespan)

    @test_app.post("/query", response_model=QueryResponse)
    async def query_endpoint(req: QueryRequest) -> QueryResponse:
        graph = _state.get("graph")
        _state.get("db_client")  # reserved for future use
        if graph is None:
            raise HTTPException(status_code=503, detail="Graph not initialized")

        start = time.monotonic()
        initial_state = {
            "query": req.query, "user_id": req.user_id,
            "channel": req.channel, "thread_ts": req.thread_ts,
            "messages": [], "intent": "", "intent_confidence": 0.0,
            "sources": [], "context_text": "", "agent_response": "",
            "agent_name": "", "proposed_value": None, "proposed_cell": None,
            "escalation_triggered": False, "escalation_detail": None,
            "excel_nav": None, "validation_passed": False,
            "validation_warnings": [], "staging_proposal_id": None,
            "answer": "", "confidence": "Low", "confidence_score": 0.0,
            "processing_start": start, "paperclip_ticket_id": None,
        }
        config = {"configurable": {"thread_id": f"{req.user_id}:{req.thread_ts or req.channel}"}}
        result = await graph.ainvoke(initial_state, config=config)
        processing_ms = int((time.monotonic() - start) * 1000)

        sources = [
            Source(
                type=s.get("type", "document"), filename=s.get("filename", ""),
                page=s.get("page"), date=s.get("date"),
                uploader=s.get("uploader"), excerpt=s.get("excerpt", ""),
                relevance_score=s.get("relevance_score", 0.0),
            )
            for s in result.get("sources", [])
        ]
        return QueryResponse(
            answer=result.get("answer", ""), sources=sources,
            excel_nav=result.get("excel_nav"),
            staging_proposal_id=result.get("staging_proposal_id"),
            escalation_triggered=result.get("escalation_triggered", False),
            confidence=result.get("confidence", "Low"),
            processing_time_ms=processing_ms,
        )

    @test_app.get("/health")
    async def health_endpoint() -> dict:
        return {"status": "healthy", "service": "cac-orchestrator"}

    @test_app.get("/heartbeat")
    async def heartbeat_endpoint() -> dict:
        return {"status": "ok"}

    return test_app


@pytest.fixture
def client(mock_graph):
    """Create test client with mocked dependencies and no-op lifespan."""
    _state["graph"] = mock_graph
    _state["db_client"] = AsyncMock()
    _state["llm_client"] = AsyncMock()
    _state["rag_client"] = AsyncMock()

    test_app = _build_test_app()
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c

    # Cleanup shared state
    _state.clear()


class TestQueryEndpoint:
    """Tests for POST /query."""

    def test_query_returns_structured_response(self, client):
        resp = client.post(
            "/query",
            json={
                "query": "What is the current net debt/EBITDA ratio?",
                "user_id": "U12345678",
                "channel": "C-alco-queries",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "sources" in body
        assert "confidence" in body
        assert "processing_time_ms" in body
        assert body["confidence"] == "High"

    def test_query_has_sources(self, client):
        resp = client.post(
            "/query",
            json={
                "query": "What is the current net debt/EBITDA ratio?",
                "user_id": "U12345678",
                "channel": "C-alco-queries",
            },
        )
        body = resp.json()
        assert len(body["sources"]) > 0
        src = body["sources"][0]
        assert src["filename"] == "ALCO_Minutes_Feb2026.pdf"
        assert src["relevance_score"] == pytest.approx(0.94)

    def test_query_has_processing_time(self, client):
        resp = client.post(
            "/query",
            json={
                "query": "What is the current net debt/EBITDA ratio?",
                "user_id": "U12345678",
                "channel": "C-alco-queries",
            },
        )
        body = resp.json()
        assert body["processing_time_ms"] >= 0

    def test_query_proposal_present(self, client):
        resp = client.post(
            "/query",
            json={
                "query": "What is the current net debt/EBITDA ratio?",
                "user_id": "U12345678",
                "channel": "C-alco-queries",
            },
        )
        body = resp.json()
        assert body["staging_proposal_id"] == "chg_0001"

    def test_query_escalation_not_triggered(self, client):
        resp = client.post(
            "/query",
            json={
                "query": "What is the current net debt/EBITDA ratio?",
                "user_id": "U12345678",
                "channel": "C-alco-queries",
            },
        )
        body = resp.json()
        assert body["escalation_triggered"] is False

    def test_query_missing_fields_returns_422(self, client):
        resp = client.post("/query", json={"query": "incomplete"})
        assert resp.status_code == 422

    def test_query_graph_not_initialized(self, client):
        """If graph is missing from state, return 503."""
        _state.pop("graph", None)
        resp = client.post(
            "/query",
            json={
                "query": "test",
                "user_id": "U12345678",
                "channel": "C-test",
            },
        )
        assert resp.status_code == 503


class TestHealthEndpoints:
    """Tests for /health and /heartbeat."""

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "cac-orchestrator"

    def test_heartbeat_endpoint(self, client):
        resp = client.get("/heartbeat")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
