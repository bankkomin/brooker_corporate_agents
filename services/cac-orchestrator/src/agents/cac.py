"""Single consolidated CAC agent.

Replaces the former liquidity/capital/alm/funding/covenant + cfo specialist
fan-out. Per the Khao Yai retreat §2.8 the CAC is ONE management committee with
one mandate and 7 Key Functions — not a set of sub-agents. This agent loads the
consolidated, doc-grounded skill at skills/cac/cac-agent.md.
"""
from __future__ import annotations

from .base import BaseAgent


class CacAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "cac-agent"

    @property
    def skill_path(self) -> str:
        return "cac/cac-agent"
