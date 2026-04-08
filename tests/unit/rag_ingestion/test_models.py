"""Tests for Pydantic request/response models."""

import pytest
from pydantic import ValidationError
from services.rag_ingestion.src.models import (
    CollectionInfo,
    CollectionsResponse,
    HealthResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
    IngestMessageRequest,
    IngestMessageResponse,
)


class TestIngestDocumentRequest:
    def test_valid_request(self) -> None:
        req = IngestDocumentRequest(file_path="/data/mirror/doc.pdf")
        assert req.file_path == "/data/mirror/doc.pdf"
        assert req.dept == "CAC"
        assert req.doc_type == "pdf"
        assert req.collection == "cac_docs"

    def test_missing_file_path_raises(self) -> None:
        with pytest.raises(ValidationError):
            IngestDocumentRequest()  # type: ignore[call-arg]

    def test_custom_metadata(self) -> None:
        req = IngestDocumentRequest(
            file_path="/data/mirror/doc.pdf",
            metadata={"uploader": "U123"},
        )
        assert req.metadata["uploader"] == "U123"


class TestIngestDocumentResponse:
    def test_ingested_response(self) -> None:
        resp = IngestDocumentResponse(status="ingested", chunks=15, file_hash="sha256:abc")
        assert resp.status == "ingested"
        assert resp.chunks == 15

    def test_skipped_response(self) -> None:
        resp = IngestDocumentResponse(status="skipped", reason="duplicate")
        assert resp.status == "skipped"
        assert resp.reason == "duplicate"


class TestIngestMessageRequest:
    def test_valid_request(self) -> None:
        req = IngestMessageRequest(
            text="meeting at 3pm",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123456",
        )
        assert req.text == "meeting at 3pm"
        assert req.thread_ts is None

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            IngestMessageRequest(text="hello")  # type: ignore[call-arg]


class TestIngestMessageResponse:
    def test_indexed_response(self) -> None:
        resp = IngestMessageResponse(indexed=True, message_id="msg_123")
        assert resp.indexed is True


class TestHealthResponse:
    def test_healthy(self) -> None:
        resp = HealthResponse(status="healthy", qdrant=True, embedder=True)
        assert resp.service == "rag-ingestion"


class TestCollectionsResponse:
    def test_collections_list(self) -> None:
        resp = CollectionsResponse(collections=[CollectionInfo(name="cac_docs", vectors_count=100)])
        assert len(resp.collections) == 1
        assert resp.collections[0].name == "cac_docs"
