"""Base agent for HR department specialists.

HR is READ-ONLY: agents answer questions with citations but never propose
staging changes or Excel writes.
"""
from __future__ import annotations

import structlog

from ..tools.llm_client import LLMClient
from ..skills.loader import SkillsLoader

logger = structlog.get_logger("hr-orchestrator.agent")


class BaseHRAgent:
    """Abstract base for HR specialist agents."""

    name: str = "hr-agent"
    skill_path: str = "hr/hr-agent"  # relative to skills_dir

    def __init__(self, llm_client: LLMClient, skills_loader: SkillsLoader) -> None:
        self._llm = llm_client
        self._skills = skills_loader

    async def run(self, state: dict) -> dict:
        """Execute the specialist agent and return analysis.

        Returns {"agent_response": str, "agent_name": str, "confidence_score": float}.
        """
        query = state.get("query", "")
        context = state.get("context_text", "")
        memory = state.get("agent_memory", "")

        # Load skill content
        skill_content = await self._skills.load_agent_skills(self.name, self.skill_path)

        system_parts = [
            f"You are {self.name}, an HR specialist AI agent.",
            "Answer the question using the provided context and your skill instructions.",
            "Always cite sources when available. Be precise and factual.",
            "HR is read-only: you NEVER propose data changes or Excel modifications.",
        ]
        if skill_content:
            system_parts.append(f"\n--- SKILL INSTRUCTIONS ---\n{skill_content}")
        if memory:
            system_parts.append(f"\n--- AGENT MEMORY ---\n{memory}")

        system_prompt = "\n\n".join(system_parts)
        # Supervisor routing: classify_intent already picked the HR sub-domain;
        # the single HR agent acts as that backend sub-agent (route-to-relevant).
        intent = state.get("intent")
        if intent and intent not in ("general",):
            system_prompt += (
                f"\n\nThis query is routed to your **{intent}** sub-agent (backend). "
                f"Answer with that sub-domain's focus, grounded in the skill and context."
            )

        user_parts = []
        if context:
            user_parts.append(f"Retrieved context:\n{context}")
        user_parts.append(f"Question: {query}")

        try:
            response = await self._llm.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "\n\n".join(user_parts)},
                ],
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as exc:
            logger.error("agent_run_failed", agent=self.name, error=str(exc))
            response = f"I encountered an error while processing your question. ({self.name})"

        return {
            "agent_response": response,
            "agent_name": self.name,
            "confidence_score": 0.7,
        }
