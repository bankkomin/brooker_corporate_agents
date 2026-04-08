"""Asset-Liability Management agent."""
from __future__ import annotations

from .base import BaseAgent


class AlmAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "alm-agent"

    @property
    def skill_path(self) -> str:
        return "cac/alm-review"
