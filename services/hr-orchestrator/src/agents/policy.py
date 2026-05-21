"""HR policy and compliance specialist agent."""
from .base import BaseHRAgent


class PolicyAgent(BaseHRAgent):
    name = "policy-agent"
    skill_path = "hr/policy"
