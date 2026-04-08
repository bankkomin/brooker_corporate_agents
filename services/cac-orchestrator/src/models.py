"""Pydantic models for cac-orchestrator service."""

from __future__ import annotations

from pydantic import BaseModel


class Source(BaseModel):
    """A source document or chat message used to support an answer."""

    type: str  # "document" | "chat" | "knowledge"
    filename: str
    page: int | None = None
    date: str | None = None
    uploader: str | None = None
    excerpt: str
    relevance_score: float


class QueryRequest(BaseModel):
    """Incoming query from a Slack user."""

    query: str
    user_id: str
    channel: str
    thread_ts: str | None = None


class QueryResponse(BaseModel):
    """Response returned to the caller after agent processing."""

    answer: str
    sources: list[Source]
    excel_nav: str | None = None
    staging_proposal_id: str | None = None
    escalation_triggered: bool = False
    confidence: str  # "High" | "Medium" | "Low"
    processing_time_ms: int


class ManifestProposal(BaseModel):
    """Staged Excel change proposal written to the manifest file."""

    id: str  # "chg_XXXX"
    created_at: str  # ISO 8601
    agent: str
    triggered_by: str
    slack_user: str
    file: str
    tab: str
    cell: str
    old_value: str | None = None
    new_value: str
    source: str
    source_excerpt: str
    confidence: float
    reasoning: str
    status: str = "pending"
    paperclip_ticket_id: str | None = None
