"""Talent acquisition / recruitment specialist agent."""
from .base import BaseHRAgent


class TalentAgent(BaseHRAgent):
    name = "talent-agent"
    skill_path = "hr/talent"
