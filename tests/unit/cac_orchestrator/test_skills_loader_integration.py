"""Integration tests for skills loader with real placeholder SKILL.md files."""
from __future__ import annotations

import pathlib

import pytest
from services.cac_orchestrator.src.skills.loader import clear_cache, load_skill

# Root of the repository (3 levels up from this file's directory)
_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.parent

SKILL_PATHS = [
    "skills/shared/escalation-protocol.md",
    "skills/shared/citation-format.md",
    "skills/cac/liquidity-analysis.md",
    "skills/cac/capital-allocation.md",
    "skills/cac/alm-review.md",
    "skills/cac/funding-facilities.md",
]


@pytest.fixture(autouse=True)
def reset_cache() -> None:
    """Clear skill cache before each test."""
    clear_cache()


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_rel_path", SKILL_PATHS)
async def test_load_real_skill_files(skill_rel_path: str) -> None:
    """Verify each placeholder skill file loads via loader.py without error."""
    full_path = str(_REPO_ROOT / skill_rel_path)
    result = await load_skill(full_path)
    # Should load successfully — non-empty string
    assert isinstance(result, str)
    assert len(result) > 0, f"Expected non-empty content for {skill_rel_path}"


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_rel_path", SKILL_PATHS)
async def test_loaded_skill_has_content(skill_rel_path: str) -> None:
    """Verify non-empty string is returned and contains frontmatter."""
    full_path = str(_REPO_ROOT / skill_rel_path)
    result = await load_skill(full_path)
    assert "---" in result, f"Expected YAML frontmatter in {skill_rel_path}"
    assert "name:" in result, f"Expected 'name:' in frontmatter of {skill_rel_path}"


@pytest.mark.asyncio
async def test_missing_skill_returns_empty() -> None:
    """Verify loader.py returns empty string for a nonexistent path."""
    result = await load_skill("/nonexistent/skills/does-not-exist.md")
    assert result == ""
