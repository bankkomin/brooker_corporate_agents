"""SKILL.md file loader for agent prompts."""
from __future__ import annotations

import os
import re

import aiofiles
import structlog

logger = structlog.get_logger("cac-orchestrator.skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_CANONICAL_RE = re.compile(r"^canonical:\s*([^\s]+)", re.MULTILINE)
_DEPRECATED_RE = re.compile(r"^deprecated:\s*true\b", re.MULTILINE | re.IGNORECASE)
_MAX_CANONICAL_HOPS = 3


class SkillsLoader:
    """Load and cache SKILL.md files for agent prompt injection."""

    def __init__(self, skills_dir: str) -> None:
        self._skills_dir = skills_dir
        self._cache: dict[str, str] = {}

    async def load_skill(self, skill_path: str, _hops: int = 0) -> str:
        """Load a SKILL.md file, strip frontmatter, cache result.

        Args:
            skill_path: Relative path without .md extension, e.g. "cac/liquidity-analysis"

        Returns:
            Skill content with frontmatter stripped. Empty string if file not found.

        If the file's frontmatter declares `deprecated: true` AND
        `canonical: skills/<path>.md`, follows the canonical pointer (with
        a hop limit to prevent cycles).
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

        # Honor `deprecated: true` + `canonical: ...` redirect (audit bug #4 fix).
        if _hops < _MAX_CANONICAL_HOPS and _DEPRECATED_RE.search(raw):
            m = _CANONICAL_RE.search(raw)
            if m:
                target = m.group(1).strip()
                # Normalise: strip leading "skills/" prefix + trailing ".md".
                target = re.sub(r"^skills/", "", target)
                target = re.sub(r"\.md$", "", target)
                logger.info("skill_canonical_redirect",
                             from_=skill_path, to=target, hops=_hops + 1)
                # Recurse — populate cache under the ORIGINAL key so subsequent
                # callers don't re-traverse.
                content = await self.load_skill(target, _hops=_hops + 1)
                self._cache[skill_path] = content
                return content

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

    async def get_skill_permissions(self, skill_path: str) -> dict:
        """Return the `permissions:` block from the skill's YAML frontmatter.

        Used by staging_writer to enforce mode='write_via_staging'. Returns
        {} (no permissions) if the file is missing or has no frontmatter.
        Honours canonical redirects same as load_skill().
        """
        full_path = os.path.join(self._skills_dir, f"{skill_path}.md")
        try:
            async with aiofiles.open(full_path, encoding="utf-8") as f:
                raw = await f.read()
        except FileNotFoundError:
            return {}

        # Honour canonical redirect (e.g. shared/cfo-agent → finance/cfo-agent)
        if _DEPRECATED_RE.search(raw):
            m = _CANONICAL_RE.search(raw)
            if m:
                target = m.group(1).strip()
                target = re.sub(r"^skills/", "", target)
                target = re.sub(r"\.md$", "", target)
                return await self.get_skill_permissions(target)

        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw, re.DOTALL)
        if not fm_match:
            return {}
        frontmatter = fm_match.group(1)
        try:
            import yaml
            data = yaml.safe_load(frontmatter) or {}
        except Exception:
            # No yaml package or parse error — best-effort regex extraction.
            return _regex_permissions(frontmatter)
        perms = data.get("permissions") or {}
        return perms if isinstance(perms, dict) else {}


def _regex_permissions(frontmatter: str) -> dict:
    """Fallback frontmatter permissions parser if PyYAML unavailable."""
    out: dict = {}
    in_perms = False
    indent = None
    for line in frontmatter.splitlines():
        if not in_perms:
            if line.strip().startswith("permissions:"):
                in_perms = True
            continue
        # End of permissions block: any line at column 0 with content
        if line and not line.startswith((" ", "\t")):
            break
        if indent is None and line.strip():
            indent = len(line) - len(line.lstrip())
        if line.strip().startswith("mode:"):
            out["mode"] = line.split(":", 1)[1].strip().strip("'\"")
    return out


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
