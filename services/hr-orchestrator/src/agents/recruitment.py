"""Recruitment / talent acquisition specialist agent."""
from .base import BaseHRAgent


class RecruitmentAgent(BaseHRAgent):
    name = "recruitment-agent"
    skill_path = "hr/recruitment"
