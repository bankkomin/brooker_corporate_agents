"""Canonical SKILL.md loader with shared-skill support.

Used by Phase 2 department orchestrators. Assembles an agent prompt from:
  1. pan-department shared skills (flat files in skills/shared/*.md),
  2. cluster skills named in the agent skill's `shared_skills` frontmatter,
  3. the agent's own skill.

Content-only rule: only skill *bodies* are concatenated. A shared skill's
frontmatter `permissions` block is never read by this loader, so it cannot
widen a consuming agent's capability — the agent's own SKILL.md frontmatter
remains the sole permission source.
"""
from __future__ import annotations

import os
import re

import aiofiles
import structlog
import yaml

logger = structlog.get_logger("shared.skills_loader")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SharedSkillNotFoundError(RuntimeError):
    """Raised when an agent declares a `shared_skills` entry that does not resolve."""


class SkillsLoader:
    """Load and cache SKILL.md files for agent prompt injection."""

    def __init__(self, skills_dir: str) -> None:
        self._skills_dir = skills_dir
        self._cache: dict[str, str] = {}
        self._fm_cache: dict[str, dict] = {}

    async def _read_raw(self, skill_path: str) -> str | None:
        full_path = os.path.join(self._skills_dir, f"{skill_path}.md")
        try:
            async with aiofiles.open(full_path, encoding="utf-8") as f:
                return await f.read()
        except FileNotFoundError:
            return None

    async def load_skill(self, skill_path: str) -> str:
        """Load a SKILL.md body (frontmatter stripped). Empty string if missing."""
        if skill_path in self._cache:
            return self._cache[skill_path]
        raw = await self._read_raw(skill_path)
        if raw is None:
            logger.warning("skill_not_found", path=skill_path, skills_dir=self._skills_dir)
            self._cache[skill_path] = ""
            return ""
        content = _FRONTMATTER_RE.sub("", raw).strip()
        self._cache[skill_path] = content
        logger.info("skill_loaded", path=skill_path, chars=len(content))
        return content

    async def load_frontmatter(self, skill_path: str) -> dict:
        """Parse and cache a SKILL.md frontmatter block. Empty dict if none/missing."""
        if skill_path in self._fm_cache:
            return self._fm_cache[skill_path]
        raw = await self._read_raw(skill_path)
        fm: dict = {}
        if raw is not None:
            m = _FRONTMATTER_RE.match(raw)
            if m:
                try:
                    parsed = yaml.safe_load(m.group(1))
                except yaml.YAMLError:
                    logger.warning("skill_frontmatter_parse_error", path=skill_path)
                    parsed = None
                if isinstance(parsed, dict):
                    fm = parsed
        self._fm_cache[skill_path] = fm
        return fm

    async def load_agent_skills(self, agent_name: str, agent_skill_path: str) -> str:
        """Assemble pan-dept shared skills + declared cluster skills + agent skill."""
        parts: list[str] = []

        # 1. Pan-department shared skills — flat files only; subdirs excluded.
        shared_dir = os.path.join(self._skills_dir, "shared")
        if os.path.isdir(shared_dir):
            for fname in sorted(os.listdir(shared_dir)):
                if fname.endswith(".md"):
                    name = f"shared/{fname[:-3]}"
                    content = await self.load_skill(name)
                    if content:
                        parts.append(f"# Shared Skill: {fname[:-3]}\n\n{content}")

        # 2. Cluster shared skills declared in the agent skill frontmatter.
        fm = await self.load_frontmatter(agent_skill_path)
        for ref in fm.get("shared_skills") or []:
            content = await self.load_skill(ref)
            if not content:
                raise SharedSkillNotFoundError(
                    f"agent '{agent_name}' declares shared_skills entry '{ref}' "
                    f"which does not resolve under {self._skills_dir}"
                )
            parts.append(f"# Shared Skill: {ref}\n\n{content}")

        # 3. Agent's own skill — last.
        agent_content = await self.load_skill(agent_skill_path)
        if agent_content:
            parts.append(f"# Agent Skill: {agent_name}\n\n{agent_content}")

        return "\n\n---\n\n".join(parts)

    def clear_cache(self) -> None:
        """Clear the in-memory skill and frontmatter caches."""
        self._cache.clear()
        self._fm_cache.clear()
