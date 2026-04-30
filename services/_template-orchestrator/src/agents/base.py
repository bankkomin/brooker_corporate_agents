"""Re-export shared BaseAgent for department orchestrators."""
# In per-dept implementation, import from services.shared or copy pattern from cac-orchestrator
# This file exists as a placeholder for the template.


class BaseSpecialistAgent:
    """Template base class for department specialist agents."""

    name: str = "{AGENT_NAME}"
    skill_path: str = "skills/{DEPT_ID}/{AGENT_NAME}.md"

    async def analyze(self, state: dict, llm_client, skill_content: str) -> dict:
        """Override in each specialist to implement domain-specific analysis."""
        raise NotImplementedError("Implement in per-dept specialist")
