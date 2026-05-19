"""Tests for Qdrant store wrapper."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from services.rag_ingestion.src.qdrant_store import COLLECTIONS, QdrantStore


@pytest.fixture
def mock_settings() -> MagicMock:
    s = MagicMock()
    s.qdrant_host = "localhost"
    s.qdrant_rest_port = 6333
    return s


@pytest.fixture
def store(mock_settings: MagicMock) -> QdrantStore:
    s = QdrantStore(mock_settings)
    s._client = AsyncMock()
    return s


class TestCollections:
    def test_collections_list_has_expected_names(self) -> None:
        _depts = ("cac", "risk", "legal", "invest", "ops", "hr", "it")
        expected = (
            [f"{d}_docs" for d in _depts]
            + [f"{d}_chat" for d in _depts]
            + [f"{d}_knowledge" for d in _depts]
            + ["shared_policies"]
        )
        assert expected == COLLECTIONS

    def test_collections_is_nonempty(self) -> None:
        assert len(COLLECTIONS) > 0


class TestEnsureCollections:
    @pytest.mark.asyncio
    async def test_creates_missing_collections(self, store: QdrantStore) -> None:
        mock_collections = MagicMock()
        mock_collections.collections = []
        store._client.get_collections.return_value = mock_collections

        await store.ensure_collections(vector_size=768)

        assert store._client.create_collection.call_count == len(COLLECTIONS)

    @pytest.mark.asyncio
    async def test_skips_existing_collections(self, store: QdrantStore) -> None:
        existing = [MagicMock(name=n) for n in COLLECTIONS]
        for e, n in zip(existing, COLLECTIONS, strict=True):
            e.name = n
        mock_collections = MagicMock()
        mock_collections.collections = existing
        store._client.get_collections.return_value = mock_collections

        await store.ensure_collections(vector_size=768)

        store._client.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_only_missing_when_some_exist(self, store: QdrantStore) -> None:
        # First two collections already exist
        existing_names = COLLECTIONS[:2]
        existing = [MagicMock() for _ in existing_names]
        for e, n in zip(existing, existing_names, strict=True):
            e.name = n
        mock_collections = MagicMock()
        mock_collections.collections = existing
        store._client.get_collections.return_value = mock_collections

        await store.ensure_collections(vector_size=768)

        assert store._client.create_collection.call_count == len(COLLECTIONS) - 2

    @pytest.mark.asyncio
    async def test_passes_vector_size_to_create(self, store: QdrantStore) -> None:
        mock_collections = MagicMock()
        mock_collections.collections = []
        store._client.get_collections.return_value = mock_collections

        await store.ensure_collections(vector_size=1024)

        first_call = store._client.create_collection.call_args_list[0]
        vectors_config = first_call.kwargs["vectors_config"]
        assert vectors_config.size == 1024


class TestUpsertChunks:
    @pytest.mark.asyncio
    async def test_upsert_batch_returns_count(self, store: QdrantStore) -> None:
        count = await store.upsert_chunks(
            collection="cac_docs",
            texts=["hello", "world"],
            vectors=[[0.1] * 4, [0.2] * 4],
            metadatas=[{"source": "a"}, {"source": "b"}],
        )
        assert count == 2
        store._client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_empty_skips_client_call(self, store: QdrantStore) -> None:
        count = await store.upsert_chunks(
            collection="cac_docs", texts=[], vectors=[], metadatas=[]
        )
        assert count == 0
        store._client.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_single_chunk(self, store: QdrantStore) -> None:
        count = await store.upsert_chunks(
            collection="cac_chat",
            texts=["single"],
            vectors=[[0.5] * 8],
            metadatas=[{"dept": "CAC"}],
        )
        assert count == 1
        store._client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_passes_collection_name(self, store: QdrantStore) -> None:
        await store.upsert_chunks(
            collection="shared_policies",
            texts=["policy text"],
            vectors=[[0.1] * 4],
            metadatas=[{}],
        )
        call_kwargs = store._client.upsert.call_args.kwargs
        assert call_kwargs["collection_name"] == "shared_policies"

    @pytest.mark.asyncio
    async def test_upsert_payload_contains_text(self, store: QdrantStore) -> None:
        await store.upsert_chunks(
            collection="cac_docs",
            texts=["important text"],
            vectors=[[0.1] * 4],
            metadatas=[{"source_file": "/data/mirror/doc.pdf"}],
        )
        call_kwargs = store._client.upsert.call_args.kwargs
        points = call_kwargs["points"]
        assert len(points) == 1
        assert points[0].payload["text"] == "important text"
        assert points[0].payload["source_file"] == "/data/mirror/doc.pdf"


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, store: QdrantStore) -> None:
        hit = MagicMock()
        hit.payload = {"text": "hello", "source": "doc.pdf"}
        hit.score = 0.85
        hit.id = "abc-123"
        store._client.search.return_value = [hit]

        results = await store.search("cac_docs", query_vector=[0.1] * 4)

        assert len(results) == 1
        assert results[0]["text"] == "hello"
        assert results[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_search_includes_id_in_result(self, store: QdrantStore) -> None:
        hit = MagicMock()
        hit.payload = {"text": "doc text"}
        hit.score = 0.90
        hit.id = "def-456"
        store._client.search.return_value = [hit]

        results = await store.search("cac_docs", query_vector=[0.2] * 4)

        assert results[0]["id"] == "def-456"

    @pytest.mark.asyncio
    async def test_search_with_filters_passes_query_filter(self, store: QdrantStore) -> None:
        store._client.search.return_value = []
        await store.search("cac_docs", query_vector=[0.1] * 4, filters={"dept": "CAC"})

        call_kwargs = store._client.search.call_args.kwargs
        assert call_kwargs.get("query_filter") is not None

    @pytest.mark.asyncio
    async def test_search_without_filters_passes_none(self, store: QdrantStore) -> None:
        store._client.search.return_value = []
        await store.search("cac_docs", query_vector=[0.1] * 4)

        call_kwargs = store._client.search.call_args.kwargs
        assert call_kwargs.get("query_filter") is None

    @pytest.mark.asyncio
    async def test_search_empty_results(self, store: QdrantStore) -> None:
        store._client.search.return_value = []
        results = await store.search("cac_docs", query_vector=[0.1] * 4)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_passes_limit(self, store: QdrantStore) -> None:
        store._client.search.return_value = []
        await store.search("cac_docs", query_vector=[0.1] * 4, limit=5)

        call_kwargs = store._client.search.call_args.kwargs
        assert call_kwargs["limit"] == 5

    @pytest.mark.asyncio
    async def test_search_passes_score_threshold(self, store: QdrantStore) -> None:
        store._client.search.return_value = []
        await store.search("cac_docs", query_vector=[0.1] * 4, score_threshold=0.90)

        call_kwargs = store._client.search.call_args.kwargs
        assert call_kwargs["score_threshold"] == 0.90

    @pytest.mark.asyncio
    async def test_search_hit_with_none_payload_returns_empty_text(
        self, store: QdrantStore
    ) -> None:
        hit = MagicMock()
        hit.payload = None
        hit.score = 0.75
        hit.id = "xyz"
        store._client.search.return_value = [hit]

        results = await store.search("cac_docs", query_vector=[0.1] * 4)

        assert results[0]["text"] == ""

    @pytest.mark.asyncio
    async def test_search_merges_payload_fields_into_result(
        self, store: QdrantStore
    ) -> None:
        hit = MagicMock()
        hit.payload = {"text": "content", "source_file": "/data/mirror/a.pdf", "dept": "CAC"}
        hit.score = 0.88
        hit.id = "ghi-789"
        store._client.search.return_value = [hit]

        results = await store.search("cac_docs", query_vector=[0.1] * 4)

        assert results[0]["source_file"] == "/data/mirror/a.pdf"
        assert results[0]["dept"] == "CAC"


class TestDeleteByFile:
    @pytest.mark.asyncio
    async def test_delete_calls_client_delete(self, store: QdrantStore) -> None:
        await store.delete_by_file("cac_docs", "/data/mirror/doc.pdf")
        store._client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_passes_collection_name(self, store: QdrantStore) -> None:
        await store.delete_by_file("cac_knowledge", "/data/mirror/policy.pdf")
        call_kwargs = store._client.delete.call_args.kwargs
        assert call_kwargs["collection_name"] == "cac_knowledge"

    @pytest.mark.asyncio
    async def test_delete_passes_points_selector_filter(self, store: QdrantStore) -> None:
        await store.delete_by_file("cac_docs", "/data/mirror/report.pdf")
        call_kwargs = store._client.delete.call_args.kwargs
        # A Filter object is passed, not None
        assert call_kwargs.get("points_selector") is not None


class TestGetCollectionInfo:
    @pytest.mark.asyncio
    async def test_returns_name_count_status(self, store: QdrantStore) -> None:
        info_mock = MagicMock()
        info_mock.vectors_count = 42
        info_mock.status = "green"
        store._client.get_collection.return_value = info_mock

        result = await store.get_collection_info("cac_docs")

        assert result["name"] == "cac_docs"
        assert result["vectors_count"] == 42
        assert result["status"] == "green"

    @pytest.mark.asyncio
    async def test_none_vectors_count_returns_zero(self, store: QdrantStore) -> None:
        info_mock = MagicMock()
        info_mock.vectors_count = None
        info_mock.status = "yellow"
        store._client.get_collection.return_value = info_mock

        result = await store.get_collection_info("cac_docs")

        assert result["vectors_count"] == 0

    @pytest.mark.asyncio
    async def test_passes_collection_name_to_client(self, store: QdrantStore) -> None:
        info_mock = MagicMock()
        info_mock.vectors_count = 0
        info_mock.status = "green"
        store._client.get_collection.return_value = info_mock

        await store.get_collection_info("shared_policies")

        store._client.get_collection.assert_called_once_with("shared_policies")


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_when_client_responds(self, store: QdrantStore) -> None:
        store._client.get_collections.return_value = MagicMock()
        assert await store.health_check() is True

    @pytest.mark.asyncio
    async def test_unhealthy_on_connection_refused(self, store: QdrantStore) -> None:
        store._client.get_collections.side_effect = Exception("connection refused")
        assert await store.health_check() is False

    @pytest.mark.asyncio
    async def test_unhealthy_on_any_exception(self, store: QdrantStore) -> None:
        store._client.get_collections.side_effect = RuntimeError("timeout")
        assert await store.health_check() is False


class TestClose:
    @pytest.mark.asyncio
    async def test_close_delegates_to_client(self, store: QdrantStore) -> None:
        await store.close()
        store._client.close.assert_called_once()
