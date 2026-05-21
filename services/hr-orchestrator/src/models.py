"""Pydantic models for hr-orchestrator service."""

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
    """Incoming query from a Slack user or web channel."""

    query: str
    user_id: str
    channel: str
    thread_ts: str | None = None
    # Gateway-forwarded slug — HR ignores this (single dept) but accepts it
    # so the gateway can use a uniform payload across all orchestrators.
    dept_id: str | None = None
    files: list[dict] = []
    auth_token: str | None = None
    portal_base_url: str | None = None


class QueryResponse(BaseModel):
    """Response returned to the caller after agent processing.

    HR is read-only: no staging_proposal_id or excel_nav fields.
    """

    answer: str
    sources: list[Source]
    escalation_triggered: bool = False
    confidence: str  # "High" | "Medium" | "Low"
    processing_time_ms: int
