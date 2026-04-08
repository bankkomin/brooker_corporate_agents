"""Liquidity analysis agent."""
from __future__ import annotations

from .base import BaseAgent


class LiquidityAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "liquidity-agent"

    @property
    def skill_path(self) -> str:
        return "cac/liquidity-analysis"
