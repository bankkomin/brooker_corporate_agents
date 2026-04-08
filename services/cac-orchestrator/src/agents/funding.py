"""Funding facilities agent."""
from __future__ import annotations

from .base import BaseAgent


class FundingAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "funding-agent"

    @property
    def skill_path(self) -> str:
        return "cac/funding-facilities"
