"""Pydantic models for email-notifier."""
from __future__ import annotations

from pydantic import BaseModel


class EscalationNotification(BaseModel):
    escalation_detail: str
    agent_name: str
    query: str
    user_id: str
    channel: str
    severity: str = "high"
    dept: str = "cac"


class ProposalNotification(BaseModel):
    proposal_id: str
    agent_name: str
    file: str
    tab: str
    cell: str
    new_value: str
    confidence: float
    dept: str


class ReminderNotification(BaseModel):
    proposal_id: str
    recipient: str
    dept: str


class ConfirmedNotification(BaseModel):
    proposal_id: str
    decision: str
    dept: str
    recipient: str | None = None
