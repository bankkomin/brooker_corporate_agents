from typing import TypedDict, Optional


class AgentState(TypedDict, total=False):
    # Input
    query: str
    user_id: str
    dept_id: str
    agent_id: str
    vault_root: str

    # Memory
    agent_memory: str

    # Classification
    intent: str
    specialist: str

    # Retrieval
    context: str
    citations: list[str]

    # Agent response
    response: str
    confidence: float

    # Staging (write-capable depts only)
    proposal_id: Optional[str]
    file: Optional[str]
    tab: Optional[str]
    cell: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    reasoning: Optional[str]

    # Escalation
    escalation_triggered: bool
    escalation_severity: Optional[str]

    # Tracking
    interaction_id: Optional[int]
