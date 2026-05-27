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
    """POST /query payload.

    `dept_id` is REQUIRED by the multi-tenant read-only-orchestrator (it serves
    many departments behind one /query). Without this field Pydantic v2 silently
    dropped the kwarg clients.py passed, so read-only depts got a 400.
    """

    query: str
    channel: str
    user_id: str
    thread_ts: str | None = None
    dept_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class PostEscalationRequest(BaseModel):
    """POST /post-escalation payload from paperclip."""

    channel: str = "#escalations"
    department: str
    escalation_detail: str
    agent_name: str = ""
    severity: str = "high"


class Citation(BaseModel):
    """Single citation in a QueryResponse.

    Tolerant of two upstream shapes:
      - cac/hr-orchestrator: {type, filename, page, excerpt, relevance_score, ...}
      - deck-writer / generic: {source, excerpt, score}
    Aliases let us accept either without further translation.
    """

    model_config = {"populate_by_name": True}

    # alias=filename lets us accept cac's Source dicts; default ""  keeps it tolerant.
    source: str = Field(default="", alias="filename")
    excerpt: str = ""
    # alias=relevance_score accepts cac's float; default 0.0 keeps it tolerant.
    score: float = Field(default=0.0, alias="relevance_score")


class QueryResponse(BaseModel):
    """Response from cac-orchestrator / read-only-orchestrator / deck-writer."""

    model_config = {"populate_by_name": True}

    answer: str = ""
    # cac-orchestrator returns `sources`; older slack-bot code reads `citations`.
    citations: list[Citation] = Field(default_factory=list, alias="sources")
    # Accepts both numeric (0.0–1.0) from orchestrators and categorical
    # ("High" | "Medium" | "Low") from deck-writer / clients.py.
    confidence: float | str = "Low"
    agent_id: str = ""
    error: str | None = None
    # deck-writer / any artefact-producing service returns these so we can
    # upload the file into the Slack thread alongside the text reply.
    file_path: str | None = None
    file_name: str | None = None
    file_url: str | None = None
