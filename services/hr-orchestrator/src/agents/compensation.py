"""Compensation and benefits specialist agent."""
from .base import BaseHRAgent


class CompensationAgent(BaseHRAgent):
    name = "compensation-agent"
    skill_path = "hr/compensation"
