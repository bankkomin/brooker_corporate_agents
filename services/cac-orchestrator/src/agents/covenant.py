"""Covenant monitoring agent."""
from __future__ import annotations

from .base import BaseAgent


class CovenantAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "covenant-agent"

    @property
    def skill_path(self) -> str:
        return "cac/covenant-monitoring"
