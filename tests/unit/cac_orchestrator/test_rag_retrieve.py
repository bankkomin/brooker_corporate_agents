"""Unit tests for retrieve_context node."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from services.cac_orchestrator.src.nodes.retrieve_context import retrieve_context


def _make_result(filename: str, page: int, excerpt: str, relevance: float) -> dict:
    return {"filename": filename, "page": page, "excerpt": excerpt, "relevance_score": relevance}


@pytest.fixture
def rag_client() -> AsyncMock:
    client = AsyncMock()
    client.search = AsyncMock(return_value=[])
    return client


async def test_retrieve_returns_sources(rag_client: AsyncMock) -> None:
    """Returns sources list matching the mock results."""
    mock_results = [
        _make_result("report.pdf", 1, "LCR is 1.2", 0.92),
        _make_result("policy.pdf", 5, "Minimum LCR 1.0", 0.81),
    ]
    rag_client.search.return_value = mock_results
    state = {"query": "What is the LCR?"}
    result = await retrieve_context(state, rag_client=rag_client)
    assert len(result["sources"]) == 2
    assert result["sources"][0]["filename"] == "report.pdf"


async def test_retrieve_deduplication(rag_client: AsyncMock) -> None:
    """Duplicate (filename, page) entries are deduplicated by the RAG client or node."""
    # The deduplication is done inside RAGClient.search — here we confirm the node
    # passes through whatever the client returns (deduplication tested at rag_client level).
    # We verify distinct filenames survive.
    mock_results = [
        _make_result("report.pdf", 1, "excerpt A", 0.95),
        _make_result("policy.pdf", 2, "excerpt B", 0.85),
    ]
    rag_client.search.return_value = mock_results
    state = {"query": "test"}
    result = await retrieve_context(state, rag_client=rag_client)
    filenames = [s["filename"] for s in result["sources"]]
    assert "report.pdf" in filenames
    assert "policy.pdf" in filenames


async def test_retrieve_sorted_by_relevance(rag_client: AsyncMock) -> None:
    """Highest relevance source appears first (RAGClient returns sorted list)."""
    mock_results = [
        _make_result("high.pdf", 1, "high relevance", 0.95),
        _make_result("low.pdf", 2, "low relevance", 0.72),
    ]
    rag_client.search.return_value = mock_results
    state = {"query": "test"}
    result = await retrieve_context(state, rag_client=rag_client)
    assert result["sources"][0]["relevance_score"] == 0.95


async def test_retrieve_min_relevance_filtering(rag_client: AsyncMock) -> None:
    """RAGClient filters by min_relevance — node passes the kwarg through."""
    rag_client.search.return_value = []
    state = {"query": "test"}
    await retrieve_context(state, rag_client=rag_client, min_relevance=0.85)
    call_kwargs = rag_client.search.call_args[1]
    assert call_kwargs["min_relevance"] == 0.85


async def test_retrieve_empty_results(rag_client: AsyncMock) -> None:
    """Empty search results produce empty sources and empty context_text."""
    rag_client.search.return_value = []
    state = {"query": "unknown topic"}
    result = await retrieve_context(state, rag_client=rag_client)
    assert result["sources"] == []
    assert result["context_text"] == ""


async def test_retrieve_formats_context_text(rag_client: AsyncMock) -> None:
    """context_text has format '[N] filename p.X: excerpt'."""
    mock_results = [
        _make_result("alco.pdf", 3, "LCR is 1.15", 0.93),
    ]
    rag_client.search.return_value = mock_results
    state = {"query": "LCR"}
    result = await retrieve_context(state, rag_client=rag_client)
    assert result["context_text"] == "[1] alco.pdf p.3: LCR is 1.15"


async def test_retrieve_uses_embed_fn(rag_client: AsyncMock) -> None:
    """When embed_fn is provided it is called with the query."""
    embed_fn = AsyncMock(return_value=[0.1] * 384)
    rag_client.search.return_value = []
    state = {"query": "covenant ratio"}
    await retrieve_context(state, rag_client=rag_client, embed_fn=embed_fn)
    embed_fn.assert_awaited_once_with("covenant ratio")


async def test_retrieve_zero_vector_fallback(rag_client: AsyncMock) -> None:
    """Without embed_fn the search is called with a zero vector of length 384."""
    rag_client.search.return_value = []
    state = {"query": "test"}
    await retrieve_context(state, rag_client=rag_client, embed_fn=None)
    call_kwargs = rag_client.search.call_args[1]
    qv = call_kwargs["query_vector"]
    assert len(qv) == 384
    assert all(v == 0.0 for v in qv)
