"""General HR agent for unclassified queries."""
from .base import BaseHRAgent


class GeneralHRAgent(BaseHRAgent):
    name = "general-hr-agent"
    skill_path = "hr/hr-agent"
