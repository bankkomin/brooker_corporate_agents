"""Pydantic models for sync-back service."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ApprovedProposal(BaseModel):
    """A proposal that has been approved and is ready for staging.

    Fields come from a JOIN between staging_proposals and approval_decisions.
    The staging_proposals PK is `id` (not proposal_id).
    approved_at / approved_by / synced_at come from approval_decisions.
    """

    proposal_id: str          # staging_proposals.id
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
    dept: str
    # From approval_decisions JOIN
    approved_at: datetime     # approval_decisions.decided_at
    approved_by: str | None = None  # approval_decisions.decided_by
    decision_synced_at: datetime | None = None  # approval_decisions.synced_at


class ArchiveRecord(BaseModel):
    """A record of a proposal moved to the archive.

    Fields come from a JOIN between staging_proposals and approval_decisions.
    decided_at / decided_by come from approval_decisions.
    archived_at is set by the archiver at runtime (not a DB column).
    """

    proposal_id: str          # staging_proposals.id
    agent: str
    file: str
    tab: str
    cell: str
    old_value: Any
    new_value: Any
    source: str
    confidence: float
    reasoning: str
    decision: str             # "approved", "rejected", "synced"
    decided_at: datetime      # approval_decisions.decided_at
    decided_by: str | None = None  # approval_decisions.decided_by
    decision_synced_at: datetime | None = None  # approval_decisions.synced_at
    archived_at: datetime
