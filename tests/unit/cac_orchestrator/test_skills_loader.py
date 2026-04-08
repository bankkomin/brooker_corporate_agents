"""Unit tests for SkillsLoader."""
from __future__ import annotations

import pytest
from services.cac_orchestrator.src.skills.loader import SkillsLoader, clear_cache, load_skill


@pytest.fixture
def skills_dir(tmp_path):  # type: ignore[no-untyped-def]
    """Create a temporary skills directory with test files."""
    shared = tmp_path / "shared"
    shared.mkdir()
    cac = tmp_path / "cac"
    cac.mkdir()

    (shared / "citation-format.md").write_text(
        "---\nname: citation-format\nagent: all\n---\n\n## Mandate\nCitation rules here."
    )
    (shared / "escalation-protocol.md").write_text(
        "---\nname: escalation-protocol\nagent: all\n---\n\n## Mandate\nEscalation rules."
    )
    (cac / "liquidity-analysis.md").write_text(
        "---\nname: liquidity-analysis\nagent: liquidity-agent\n"
        "---\n\n## Mandate\nLiquidity analysis."
    )
    return str(tmp_path)


# --- SkillsLoader class tests ---


@pytest.mark.asyncio
async def test_load_skill_strips_frontmatter(skills_dir: str) -> None:
    loader = SkillsLoader(skills_dir)
    content = await loader.load_skill("shared/citation-format")
    assert "---" not in content
    assert "name: citation-format" not in content
    assert "## Mandate" in content
    assert "Citation rules here." in content


@pytest.mark.asyncio
async def test_load_skill_caches(skills_dir: str) -> None:
    loader = SkillsLoader(skills_dir)
    content1 = await loader.load_skill("shared/citation-format")
    content2 = await loader.load_skill("shared/citation-format")
    assert content1 == content2
    assert "shared/citation-format" in loader._cache


@pytest.mark.asyncio
async def test_load_skill_missing_returns_empty(skills_dir: str) -> None:
    loader = SkillsLoader(skills_dir)
    content = await loader.load_skill("cac/nonexistent")
    assert content == ""


@pytest.mark.asyncio
async def test_load_agent_skills_combines_shared_and_agent(skills_dir: str) -> None:
    loader = SkillsLoader(skills_dir)
    content = await loader.load_agent_skills("liquidity-agent", "cac/liquidity-analysis")
    assert "Citation rules here." in content
    assert "Escalation rules." in content
    assert "Liquidity analysis." in content


@pytest.mark.asyncio
async def test_clear_cache(skills_dir: str) -> None:
    loader = SkillsLoader(skills_dir)
    await loader.load_skill("shared/citation-format")
    assert len(loader._cache) > 0
    loader.clear_cache()
    assert len(loader._cache) == 0


# --- Backward-compatible API tests ---


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_cache()


@pytest.mark.asyncio
async def test_legacy_load_skill_reads_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    content = "# Test skill content"
    f = tmp_path / "test.md"
    f.write_text(content)
    result = await load_skill(str(f))
    assert result == content


@pytest.mark.asyncio
async def test_legacy_load_skill_missing() -> None:
    result = await load_skill("/nonexistent/path/SKILL.md")
    assert result == ""
