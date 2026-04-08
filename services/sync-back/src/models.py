"""Pydantic models for sync-back service."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ApprovedProposal(BaseModel):
    """A proposal that has been approved and is ready for staging."""

    proposal_id: str
    agent: str
    file: str
    tab: str
    cell: str
    old_value: Any
    new_value: Any
    source: str
    confidence: float
    reasoning: str
    status: str
    approved_at: datetime
    approved_by: str | None = None


class ArchiveRecord(BaseModel):
    """A record of a proposal moved to the archive."""

    proposal_id: str
    agent: str
    file: str
    tab: str
    cell: str
    old_value: Any
    new_value: Any
    source: str
    confidence: float
    reasoning: str
    decision: str  # "approved", "rejected", "synced"
    decided_at: datetime
    decided_by: str | None = None
    archived_at: datetime
