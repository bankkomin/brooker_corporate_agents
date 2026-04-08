# tests/integration/test_rag_pipeline.py
"""Integration test for RAG ingestion pipeline."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from services.rag_ingestion.src.chunker import TextChunk
from services.rag_ingestion.src.main import app


@pytest.fixture
def mock_embedder() -> AsyncMock:
    e = AsyncMock()
    e.embed_texts.return_value = [[0.1] * 4, [0.2] * 4]
    e.embed_single.return_value = [0.1] * 4
    e.get_dimension.return_value = 4
    e.health_check.return_value = True
    e.start = AsyncMock()
    e.close = AsyncMock()
    return e


@pytest.fixture
def mock_store() -> AsyncMock:
    s = AsyncMock()
    s.upsert_chunks.return_value = 2
    s.search.return_value = []
    s.health_check.return_value = True
    s.ensure_collections = AsyncMock()
    s.close = AsyncMock()
    s.get_collection_info.return_value = {"vectors_count": 42, "status": "green"}
    return s


@pytest.fixture
def mock_chat_indexer() -> AsyncMock:
    ci = AsyncMock()
    ci.index_message.return_value = "msg_abc123"
    return ci


@pytest.fixture
def mock_chunker() -> AsyncMock:
    c = AsyncMock()
    c.chunk_file.return_value = [
        TextChunk("chunk 1", {"source_file": "test.pdf", "doc_type": "pdf"}),
        TextChunk("chunk 2", {"source_file": "test.pdf", "doc_type": "pdf"}),
    ]
    return c


@pytest.fixture
async def client(
    mock_embedder: AsyncMock,
    mock_store: AsyncMock,
    mock_chat_indexer: AsyncMock,
    mock_chunker: AsyncMock,
) -> AsyncClient:
    # Bypass lifespan by setting app.state directly before the transport is used.
    # ASGITransport sends HTTP requests directly without triggering lifespan events.
    app.state.embedder = mock_embedder
    app.state.store = mock_store
    app.state.chat_indexer = mock_chat_indexer
    app.state.chunker = mock_chunker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestDocumentIngestion:
    async def test_upload_pdf_returns_ingested_status(
        self, client: AsyncClient, mock_store: AsyncMock
    ) -> None:
        resp = await client.post(
            "/ingest/document",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            data={"dept": "CAC", "doc_type": "pdf", "collection": "cac_docs"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"
        assert data["chunks"] == 2
        assert len(data["file_hash"]) == 64

    async def test_upload_pdf_calls_store_upsert(
        self, client: AsyncClient, mock_store: AsyncMock
    ) -> None:
        await client.post(
            "/ingest/document",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            data={"dept": "CAC", "doc_type": "pdf", "collection": "cac_docs"},
        )
        mock_store.upsert_chunks.assert_awaited_once()
        call_kwargs = mock_store.upsert_chunks.call_args
        assert call_kwargs.kwargs["collection"] == "cac_docs"

    async def test_upload_empty_file_returns_skipped(
        self,
        client: AsyncClient,
        mock_chunker: AsyncMock,
    ) -> None:
        mock_chunker.chunk_file.return_value = []
        resp = await client.post(
            "/ingest/document",
            files={"file": ("empty.pdf", b"", "application/pdf")},
            data={"dept": "CAC", "doc_type": "pdf", "collection": "cac_docs"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert data["reason"] == "no chunks extracted"

    async def test_upload_returns_sha256_file_hash(self, client: AsyncClient) -> None:
        import hashlib

        content = b"deterministic content"
        expected_hash = hashlib.sha256(content).hexdigest()
        resp = await client.post(
            "/ingest/document",
            files={"file": ("doc.pdf", content, "application/pdf")},
            data={"dept": "CAC", "doc_type": "pdf", "collection": "cac_docs"},
        )
        assert resp.json()["file_hash"] == expected_hash


class TestMessageIngestion:
    async def test_index_message_returns_indexed_true(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/ingest/message",
            json={
                "text": "Meeting at 3pm",
                "author": "U123",
                "channel_id": "C456",
                "timestamp": "1234567890.123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["indexed"] is True
        assert data["message_id"] == "msg_abc123"

    async def test_index_message_calls_chat_indexer(
        self, client: AsyncClient, mock_chat_indexer: AsyncMock
    ) -> None:
        await client.post(
            "/ingest/message",
            json={
                "text": "Budget approved",
                "author": "U999",
                "channel_id": "C111",
                "timestamp": "1111111111.000",
            },
        )
        mock_chat_indexer.index_message.assert_awaited_once_with(
            text="Budget approved",
            author="U999",
            channel_id="C111",
            timestamp="1111111111.000",
            thread_ts=None,
            dept="CAC",
        )

    async def test_index_message_failure_returns_indexed_false(
        self, client: AsyncClient, mock_chat_indexer: AsyncMock
    ) -> None:
        mock_chat_indexer.index_message.side_effect = RuntimeError("downstream failure")
        resp = await client.post(
            "/ingest/message",
            json={
                "text": "Will fail",
                "author": "U000",
                "channel_id": "C000",
                "timestamp": "0000000000.000",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["indexed"] is False
        assert data["message_id"] == ""


class TestHealthEndpoint:
    async def test_healthy_when_all_services_up(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["qdrant"] is True
        assert data["embedder"] is True

    async def test_degraded_when_qdrant_down(
        self, client: AsyncClient, mock_store: AsyncMock
    ) -> None:
        mock_store.health_check.return_value = False
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["qdrant"] is False

    async def test_degraded_when_embedder_down(
        self, client: AsyncClient, mock_embedder: AsyncMock
    ) -> None:
        mock_embedder.health_check.return_value = False
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["embedder"] is False

    async def test_health_service_field_present(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.json()["service"] == "rag-ingestion"


class TestCollectionsEndpoint:
    async def test_list_all_four_collections(self, client: AsyncClient) -> None:
        resp = await client.get("/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["collections"]) == 4

    async def test_collections_have_correct_vector_count(self, client: AsyncClient) -> None:
        resp = await client.get("/collections")
        data = resp.json()
        assert data["collections"][0]["vectors_count"] == 42

    async def test_collections_include_expected_names(self, client: AsyncClient) -> None:
        resp = await client.get("/collections")
        names = {c["name"] for c in resp.json()["collections"]}
        assert names == {"cac_docs", "cac_chat", "cac_knowledge", "shared_policies"}

    async def test_collection_info_error_returns_zero_count(
        self, client: AsyncClient, mock_store: AsyncMock
    ) -> None:
        mock_store.get_collection_info.side_effect = RuntimeError("qdrant unavailable")
        resp = await client.get("/collections")
        assert resp.status_code == 200
        data = resp.json()
        # All collections should fall back to zero on error
        assert all(c["vectors_count"] == 0 for c in data["collections"])
