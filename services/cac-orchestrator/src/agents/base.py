"""Base agent ABC for specialist agents."""
from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod

import structlog

from ..skills.loader import SkillsLoader
from ..tools.llm_client import LLMClient

logger = structlog.get_logger("cac-orchestrator.agent")

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


class BaseAgent(ABC):
    """Abstract base class for specialist CAC agents with LLM + skills."""

    def __init__(self, llm_client: LLMClient, skills_loader: SkillsLoader) -> None:
        self._llm = llm_client
        self._skills = skills_loader

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier (e.g., 'liquidity-agent')."""
        ...

    @property
    @abstractmethod
    def skill_path(self) -> str:
        """Relative path to agent's SKILL.md (e.g., 'cac/liquidity-analysis')."""
        ...

    async def analyze(self, state: dict) -> dict:
        """Analyze query using SKILL.md + RAG context + LLM.

        Returns: {"agent_response": str, "agent_name": str,
                  "proposed_value": str|None, "proposed_cell": str|None,
                  "proposed_tab": str|None, "confidence_score": float}
        """
        system_prompt = await self._build_system_prompt()
        user_prompt = self._build_user_prompt(state)

        try:
            raw = await self._llm.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            return self._parse_response(raw)
        except Exception as exc:
            logger.error("agent_llm_failed", agent=self.name, error=str(exc))
            return {
                "agent_response": f"Analysis unavailable due to processing error: {exc}",
                "agent_name": self.name,
                "proposed_value": None,
                "proposed_cell": None,
                "proposed_tab": None,
                "confidence_score": 0.0,
            }

    async def run(self, state: dict) -> dict:
        """Execute with timing and logging."""
        start = time.monotonic()
        result = await self.analyze(state)
        elapsed = (time.monotonic() - start) * 1000
        logger.info("agent_complete", agent=self.name, elapsed_ms=round(elapsed, 1))
        return result

    async def _build_system_prompt(self) -> str:
        """Load agent skill + shared skills, compose system prompt."""
        skills_content = await self._skills.load_agent_skills(self.name, self.skill_path)
        header = (
            f"You are {self.name}, a specialist agent"
            " for the Capital Allocation & ALCO Committee."
        )
        proposed_line = (
            '- "proposed_change": null OR'
            ' {"value": "...", "cell": "...", "tab": "...", "reasoning": "..."}'
        )
        return (
            f"{header}\n\n"
            f"Your domain knowledge and rules:\n\n{skills_content}\n\n"
            "Respond with a JSON object containing:\n"
            '- "analysis": your detailed response with [Source: ...] citations\n'
            f"{proposed_line}\n"
            '- "confidence": float 0.0-1.0\n'
            '- "escalation_flags": list of strings (empty if none)\n\n'
            "If you are not confident enough to propose a change, set proposed_change to null."
        )

    def _build_user_prompt(self, state: dict) -> str:
        """Compose user prompt from query + RAG context + history."""
        parts = [f"User query: {state.get('query', '')}"]

        context = state.get("context_text", "")
        if context:
            parts.append(f"\nRetrieved context:\n{context}")

        messages = state.get("messages", [])
        if messages:
            history_lines = []
            for m in messages[-5:]:
                # Messages may be BaseMessage objects (live) or plain dicts
                # (deserialised from the PostgresSaver checkpointer).
                if isinstance(m, dict):
                    msg_type = m.get("type", "unknown")
                    msg_content = m.get("content", str(m))
                else:
                    msg_type = getattr(m, "type", "unknown")
                    msg_content = getattr(m, "content", str(m))
                history_lines.append(f"- {msg_type}: {msg_content}")
            parts.append("\nConversation history:\n" + "\n".join(history_lines))

        sources = state.get("sources", [])
        if sources:
            src_lines = []
            for s in sources[:5]:
                fname = s.get("filename", "unknown")
                score = s.get("relevance_score", 0)
                src_lines.append(f"- {fname} (relevance: {score:.2f})")
            parts.append("\nAvailable sources:\n" + "\n".join(src_lines))

        return "\n".join(parts)

    def _parse_response(self, raw: str) -> dict:
        """Parse LLM JSON response with fallback."""
        match = _JSON_BLOCK_RE.search(raw)
        text = match.group(1) if match else raw

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "agent_json_parse_failed", agent=self.name, raw_content=raw[:500]
            )
            return {
                "agent_response": raw,
                "agent_name": self.name,
                "proposed_value": None,
                "proposed_cell": None,
                "proposed_tab": None,
                "confidence_score": 0.5,
            }

        proposed = data.get("proposed_change")
        return {
            "agent_response": data.get("analysis", raw),
            "agent_name": self.name,
            "proposed_value": proposed.get("value") if proposed else None,
            "proposed_cell": proposed.get("cell") if proposed else None,
            "proposed_tab": proposed.get("tab") if proposed else None,
            "confidence_score": float(data.get("confidence", 0.5)),
        }
