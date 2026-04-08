"""Pydantic request/response schemas for rag-ingestion API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestDocumentRequest(BaseModel):
    file_path: str = Field(..., description="Path to the file to ingest")
    dept: str = Field(default="CAC", description="Department code")
    doc_type: str = Field(default="pdf", description="Document type: pdf|xlsx|docx|txt|md")
    collection: str = Field(default="cac_docs", description="Target Qdrant collection")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class IngestDocumentResponse(BaseModel):
    status: str = Field(..., description="ingested|skipped|error")
    chunks: int = Field(default=0, description="Number of chunks created")
    file_hash: str = Field(default="", description="SHA-256 hash of the file")
    reason: str = Field(default="", description="Reason if skipped or error")


class IngestMessageRequest(BaseModel):
    text: str = Field(..., description="Message text content")
    author: str = Field(..., description="Slack user ID")
    channel_id: str = Field(..., description="Slack channel ID")
    timestamp: str = Field(..., description="Message timestamp")
    dept: str = Field(default="CAC", description="Department code")
    thread_ts: str | None = Field(default=None, description="Thread parent timestamp")


class IngestMessageResponse(BaseModel):
    indexed: bool
    message_id: str


class HealthResponse(BaseModel):
    status: str
    qdrant: bool
    embedder: bool
    service: str = "rag-ingestion"


class CollectionInfo(BaseModel):
    name: str
    vectors_count: int


class CollectionsResponse(BaseModel):
    collections: list[CollectionInfo]
