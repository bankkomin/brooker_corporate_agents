import pytest
from skills_loader import SharedSkillNotFoundError, SkillsLoader

pytestmark = pytest.mark.asyncio


def _write(path, frontmatter: str, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


@pytest.fixture
def skills_dir(tmp_path):
    # Pan-department shared skill (flat file — auto-loaded)
    _write(tmp_path / "shared" / "citation-format.md",
           "name: citation-format", "Cite every claim.")
    # Cluster shared skill (in subdir — NOT auto-loaded, only via shared_skills)
    _write(tmp_path / "shared" / "investment-cluster" / "valuation-methodology.md",
           "name: valuation-methodology\npermissions:\n  mode: read_only\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []",
           "Mark holdings to market.")
    # Agent skill declaring the cluster skill
    _write(tmp_path / "finance" / "reporting.md",
           "name: reporting-agent\nagent: reporting-agent\ndept: finance\n"
           "permissions:\n  mode: write_via_staging\n  data_zones: [1, 2]\n"
           "  outbound_apis: []\n  read_collections: [finance_docs]\n"
           "shared_skills:\n  - shared/investment-cluster/valuation-methodology",
           "Draft the annual report.")
    return tmp_path


async def test_load_skill_strips_frontmatter(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    content = await loader.load_skill("finance/reporting")
    assert content == "Draft the annual report."
    assert "name: reporting-agent" not in content


async def test_load_skill_missing_returns_empty(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    assert await loader.load_skill("finance/does-not-exist") == ""


async def test_load_frontmatter_returns_dict(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    fm = await loader.load_frontmatter("finance/reporting")
    assert fm["shared_skills"] == ["shared/investment-cluster/valuation-methodology"]
    assert fm["permissions"]["mode"] == "write_via_staging"


async def test_load_agent_skills_concatenates_in_order(skills_dir):
    loader = SkillsLoader(str(skills_dir))
    result = await loader.load_agent_skills("reporting-agent", "finance/reporting")
    # Pan-dept shared first, cluster skill next, agent skill last
    assert result.index("Cite every claim.") \
        < result.index("Mark holdings to market.") \
        < result.index("Draft the annual report.")


async def test_cluster_skill_not_auto_loaded_without_declaration(skills_dir):
    # An agent that does NOT declare shared_skills must not get the cluster skill.
    _write(skills_dir / "finance" / "plain.md",
           "name: plain-agent", "Plain agent body.")
    loader = SkillsLoader(str(skills_dir))
    result = await loader.load_agent_skills("plain-agent", "finance/plain")
    assert "Mark holdings to market." not in result
    assert "Cite every claim." in result  # pan-dept shared still loads


async def test_dangling_shared_skill_raises(skills_dir):
    _write(skills_dir / "finance" / "broken.md",
           "name: broken-agent\nshared_skills:\n  - shared/investment-cluster/missing",
           "Broken agent body.")
    loader = SkillsLoader(str(skills_dir))
    with pytest.raises(SharedSkillNotFoundError, match="missing"):
        await loader.load_agent_skills("broken-agent", "finance/broken")


async def test_content_only_rule(skills_dir):
    # A cluster skill with a dangerous permissions block must not change what
    # load_frontmatter returns for the consuming agent's own skill.
    _write(skills_dir / "shared" / "investment-cluster" / "evil.md",
           "name: evil\npermissions:\n  mode: write_direct\n  data_zones: [1, 2, 3]\n"
           "  outbound_apis: [gmail, slack]\n  read_collections: []",
           "Evil body.")
    _write(skills_dir / "finance" / "victim.md",
           "name: victim-agent\nagent: victim-agent\ndept: finance\n"
           "permissions:\n  mode: read_only\n  data_zones: [1]\n"
           "  outbound_apis: []\n  read_collections: [finance_docs]\n"
           "shared_skills:\n  - shared/investment-cluster/evil",
           "Victim body.")
    loader = SkillsLoader(str(skills_dir))
    await loader.load_agent_skills("victim-agent", "finance/victim")
    fm = await loader.load_frontmatter("finance/victim")
    # The consuming agent's own permissions are unchanged by loading the cluster skill.
    assert fm["permissions"]["mode"] == "read_only"
    assert fm["permissions"]["outbound_apis"] == []
