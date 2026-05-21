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


class AttachedFile(BaseModel):
    """A portal-uploaded file attached to this chat turn.

    The orchestrator fetches it from `portal_base_url/api/paperclip/files/<id>`
    using `auth_token` so the content can be injected into the LLM context.
    """

    id: str
    name: str | None = None
    mimetype: str | None = None
    size: int | None = None


class QueryRequest(BaseModel):
    """Incoming query from a Slack user or web channel."""

    query: str
    user_id: str
    channel: str
    thread_ts: str | None = None
    # Gateway forwards the resolved dept slug so a single orchestrator image
    # can serve multiple departments when deployed accordingly. When unset,
    # the orchestrator uses settings.dept_id.
    dept_id: str | None = None
    files: list[AttachedFile] = []
    auth_token: str | None = None
    portal_base_url: str | None = None


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
