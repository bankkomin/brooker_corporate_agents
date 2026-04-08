"""Capital allocation agent."""
from __future__ import annotations

from .base import BaseAgent


class CapitalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "capital-agent"

    @property
    def skill_path(self) -> str:
        return "cac/capital-allocation"
