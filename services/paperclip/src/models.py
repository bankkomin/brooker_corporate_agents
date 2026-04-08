"""Pydantic v2 models for Paperclip service."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TicketCreate(BaseModel):
    """Request to create a new Paperclip ticket."""
    type: Literal["query", "proposal", "escalation", "skill_task"]
    department: str = "cac"
    agent: str
    interaction_id: str | None = None
    payload: dict


class TicketUpdate(BaseModel):
    """Request to update an existing ticket."""
    status: Literal[
        "open", "in_progress", "pending_approval",
        "completed", "rejected", "escalated",
        "pending_human", "failed",
    ] | None = None
    result: dict | None = None
    assigned_worker: str | None = None


class TicketResponse(BaseModel):
    """Ticket data returned from API."""
    ticket_id: str
    type: str
    department: str
    agent: str
    status: Literal[
        "open", "in_progress", "pending_approval",
        "completed", "rejected", "escalated",
        "pending_human", "failed",
    ]
    payload: dict
    result: dict | None = None
    assigned_worker: str | None = None
    created_at: datetime
    updated_at: datetime


class HeartbeatRequest(BaseModel):
    """Agent heartbeat registration request."""
    agent_name: str
    department: str = "cac"
    agent_role: Literal["orchestrator", "specialist", "worker"]
    endpoint_url: str | None = None
    skills: list[str] = []
    data_scope: dict = {}
    permissions: dict = {}


class HeartbeatResponse(BaseModel):
    """Agent heartbeat registration response."""
    agent_name: str
    department: str
    status: str
    last_heartbeat: datetime


class ApprovalWebhook(BaseModel):
    """Webhook payload from approval-ui."""
    proposal_id: str
    decision: Literal["approved", "rejected", "deferred"]
    reviewer: str
    timestamp: datetime
    notes: str | None = None
    edited_values: dict | None = None


class DepartmentCreate(BaseModel):
    """Request to register a new department."""
    name: str
    display_name: str
    slack_channel: str
    hod_email: str
    escalation_rules: dict = {}
    data_zone: dict
    config: dict = {}


class DepartmentResponse(BaseModel):
    """Department data returned from API."""
    id: str
    name: str
    display_name: str
    slack_channel: str
    hod_email: str
    data_zone: dict
    agent_count: int = 0
    created_at: datetime


class AgentRegister(BaseModel):
    """Request to register an agent to a department."""
    agent_name: str
    agent_role: Literal["orchestrator", "specialist", "worker"]
    worker_type: Literal["claude_code", "claude_sdk", "human", "stub"] | None = None
    endpoint_url: str | None = None
    skills: list[str] = []
    data_scope: dict = {}
    permissions: dict = {}


class AgentResponse(BaseModel):
    """Agent data returned from API."""
    agent_name: str
    department: str
    agent_role: str
    worker_type: str | None = None
    endpoint_url: str | None = None
    skills: list[str]
    status: str
    last_heartbeat: datetime | None = None
