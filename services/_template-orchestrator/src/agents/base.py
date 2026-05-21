"""Template specialist agent base.

For write-capable depts, mirror `services/cac-orchestrator/src/agents/base.py`.
For read-only depts, mirror `services/hr-orchestrator/src/agents/base.py`.

Both real bases inject a system prompt assembled from a SKILL.md and call
an LLM client; the only meaningful difference is whether `proposed_change`
appears in the agent's output schema.
"""
from __future__ import annotations


class BaseSpecialistAgent:
    """Minimal contract every specialist must satisfy.

    A concrete specialist sets `name` and `skill_path`, then calls the LLM
    with the system prompt assembled from the SKILL.md.

    Replace this with a real implementation copied from cac-orchestrator
    or hr-orchestrator when scaffolding a new dept.
    """

    name: str = "template-specialist"  # TODO: <specialist>-agent
    skill_path: str = "template/specialist-1"  # TODO: relative path under skills/

    async def run(self, state: dict) -> dict:
        """Execute the specialist for one turn and return its contribution to state.

        Expected return keys (write-capable depts):
            agent_response: str
            agent_name: str
            proposed_value: str | None
            proposed_cell: str | None
            proposed_tab: str | None
            confidence_score: float

        Read-only depts can omit the four proposed_* keys.
        """
        raise NotImplementedError(
            "Replace BaseSpecialistAgent with a concrete BaseAgent copied from "
            "cac-orchestrator or hr-orchestrator before deploying."
        )
