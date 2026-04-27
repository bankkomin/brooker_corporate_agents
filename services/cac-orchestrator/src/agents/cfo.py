"""CFO cross-domain synthesis agent."""
from __future__ import annotations

import structlog

from .base import BaseAgent

logger = structlog.get_logger("cac-orchestrator.cfo-agent")


class CFOAgent(BaseAgent):
    """Whole-of-firm synthesiser.

    The graph routes to exactly one agent per query (serial, not fan-out).
    When the CFO is the routed agent it reads whatever single specialist output
    may have been written to state by a prior run on the same thread, plus
    full RAG context, to produce a board-level composite risk view.
    It never proposes individual cell updates.
    """

    @property
    def name(self) -> str:
        return "cfo-agent"

    @property
    def skill_path(self) -> str:
        # Skill file: skills/shared/cfo-agent.md
        return "shared/cfo-agent"

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def _build_user_prompt(self, state: dict) -> str:
        """Extend the base prompt with the previous specialist's output (if any)."""
        base = super()._build_user_prompt(state)

        # The graph runs one agent per invocation.  If a specialist ran earlier
        # in the same thread, its output sits in agent_response / agent_name.
        agent_response = state.get("agent_response", "")
        agent_name = state.get("agent_name", "")

        specialist_section = ""
        if agent_response and agent_name and agent_name != self.name:
            specialist_section = (
                f"\nPrevious specialist output ({agent_name}):\n{agent_response}"
            )
        else:
            logger.warning(
                "cfo_no_prior_specialist_output",
                msg="CFO agent found no prior specialist output in state; "
                "synthesising from RAG context only.",
            )

        parts = [base]
        if specialist_section:
            parts.append(specialist_section)

        parts.append(
            "\nProvide a board-level composite risk view. "
            "Synthesise across all available domain context. "
            "Set proposed_change to null — do not propose individual cell updates."
        )

        return "\n".join(parts)

    def _parse_response(self, raw: str) -> dict:
        """Parse CFO response and enforce the no-cell-proposal rule."""
        result = super()._parse_response(raw)

        # Hard rule from skill file: CFO never proposes individual cell changes.
        result["proposed_value"] = None
        result["proposed_cell"] = None
        result["proposed_tab"] = None

        return result
