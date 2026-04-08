"""SKILL.md file loader for agent prompts."""
from __future__ import annotations

import os
import re

import aiofiles
import structlog

logger = structlog.get_logger("cac-orchestrator.skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


class SkillsLoader:
    """Load and cache SKILL.md files for agent prompt injection."""

    def __init__(self, skills_dir: str) -> None:
        self._skills_dir = skills_dir
        self._cache: dict[str, str] = {}

    async def load_skill(self, skill_path: str) -> str:
        """Load a SKILL.md file, strip frontmatter, cache result.

        Args:
            skill_path: Relative path without .md extension, e.g. "cac/liquidity-analysis"

        Returns:
            Skill content with frontmatter stripped. Empty string if file not found.
        """
        if skill_path in self._cache:
            return self._cache[skill_path]

        full_path = os.path.join(self._skills_dir, f"{skill_path}.md")
        try:
            async with aiofiles.open(full_path, encoding="utf-8") as f:
                raw = await f.read()
        except FileNotFoundError:
            logger.warning("skill_not_found", path=full_path)
            self._cache[skill_path] = ""
            return ""

        content = _FRONTMATTER_RE.sub("", raw).strip()
        self._cache[skill_path] = content
        logger.info("skill_loaded", path=skill_path, chars=len(content))
        return content

    async def load_agent_skills(self, agent_name: str, agent_skill_path: str) -> str:
        """Load agent-specific skill + all shared skills, concatenated.

        Args:
            agent_name: Agent identifier (e.g. "liquidity-agent")
            agent_skill_path: Relative path to agent's skill (e.g. "cac/liquidity-analysis")

        Returns:
            Concatenated skill content: shared skills + agent skill.
        """
        parts: list[str] = []

        # Load all shared skills
        shared_dir = os.path.join(self._skills_dir, "shared")
        if os.path.isdir(shared_dir):
            for fname in sorted(os.listdir(shared_dir)):
                if fname.endswith(".md"):
                    skill_name = f"shared/{fname[:-3]}"
                    content = await self.load_skill(skill_name)
                    if content:
                        parts.append(f"# Shared Skill: {fname[:-3]}\n\n{content}")

        # Load agent-specific skill
        agent_content = await self.load_skill(agent_skill_path)
        if agent_content:
            parts.append(f"# Agent Skill: {agent_name}\n\n{agent_content}")

        return "\n\n---\n\n".join(parts)

    def clear_cache(self) -> None:
        """Clear the in-memory skill cache."""
        self._cache.clear()


# --- Backward-compatible module-level API (deprecated) ---
_default_cache: dict[str, str] = {}


async def load_skill(skill_path: str) -> str:
    """Deprecated: Use SkillsLoader class instead."""
    if skill_path in _default_cache:
        return _default_cache[skill_path]
    try:
        async with aiofiles.open(skill_path, encoding="utf-8") as f:
            content = await f.read()
        _default_cache[skill_path] = content
        return content
    except FileNotFoundError:
        logger.warning("skill_not_found", path=skill_path)
        _default_cache[skill_path] = ""
        return ""


def clear_cache() -> None:
    """Deprecated: Use SkillsLoader.clear_cache() instead."""
    _default_cache.clear()
