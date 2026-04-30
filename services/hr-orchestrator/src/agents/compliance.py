"""HR compliance and policy specialist agent."""
from .base import BaseHRAgent


class ComplianceAgent(BaseHRAgent):
    name = "compliance-agent"
    skill_path = "hr/compliance"
