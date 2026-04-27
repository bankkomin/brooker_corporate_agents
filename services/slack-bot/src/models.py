"""Pydantic v2 schemas for slack-bot internal and external payloads."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ── Slack inbound ────────────────────────────────────────────────────

class SlackFileInfo(BaseModel):
    """Subset of Slack's file object needed for download."""

    id: str
    name: str
    mimetype: str
    url_private_download: str
    size: int
    filetype: str


# ── Outbound to rag-ingestion ────────────────────────────────────────

class IngestMessageRequest(BaseModel):
    """POST /ingest/message payload."""

    text: str
    author: str
    channel_id: str
    timestamp: str
    dept: str = "CAC"
    thread_ts: str | None = None


# ── Outbound to cac-orchestrator ─────────────────────────────────────

class QueryRequest(BaseModel):
    """POST /query payload."""

    query: str
    channel: str
    user_id: str
    thread_ts: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class PostEscalationRequest(BaseModel):
    """POST /post-escalation payload from paperclip."""

    channel: str = "#escalations"
    department: str
    escalation_detail: str
    agent_name: str = ""
    severity: str = "high"


class Citation(BaseModel):
    """Single citation in a QueryResponse."""

    source: str
    excerpt: str
    score: float


class QueryResponse(BaseModel):
    """Response from cac-orchestrator."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    agent_id: str = ""
    error: str | None = None
