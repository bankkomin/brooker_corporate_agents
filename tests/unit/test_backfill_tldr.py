"""Unit tests for scripts/backfill_tldr.py — pure-function pieces only."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "backfill_tldr.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("backfill_tldr", SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules["backfill_tldr"] = m
    spec.loader.exec_module(m)
    return m


def test_script_exists():
    assert SCRIPT.is_file()


def test_parse_audit_todo_extracts_tldr_rows(mod, tmp_path: Path):
    audit = tmp_path / "todo.md"
    audit.write_text(
        "# Vault Convention Backfill TODO\n\n"
        "## Summary\n- foo\n\n"
        "## Backlog\n\n"
        "### cac *(2 notes)*\n\n"
        "**concepts/** (2)\n"
        "- [ ] `cac/concepts/lcr.md` — `tldr`\n"
        "- [ ] `cac/concepts/nsfr.md` — `tldr` `event_date`\n"
        "- [ ] `cac/concepts/no-tldr.md` — `event_date`\n"
        "\n",
        encoding="utf-8",
    )
    items = mod.parse_audit_todo(audit)
    paths = [i.rel_path for i in items]
    assert "cac/concepts/lcr.md" in paths
    assert "cac/concepts/nsfr.md" in paths
    assert "cac/concepts/no-tldr.md" not in paths  # missing tldr code
    # nsfr has both codes
    nsfr = next(i for i in items if i.rel_path.endswith("nsfr.md"))
    assert "tldr" in nsfr.codes
    assert "event_date" in nsfr.codes


def test_has_tldr_detects_section(mod):
    body_with = "## Summary\nx\n\n## TL;DR for Agents\n**Retrieved by:** y\n"
    body_without = "## Summary\nx\n\n## Definition\ny\n"
    assert mod.has_tldr(body_with)
    assert not mod.has_tldr(body_without)


def test_insert_tldr_places_after_title_heading(mod):
    full = (
        "---\ntype: concept\n---\n\n"
        "# LCR\n\n"
        "## Summary\nLiquidity Coverage Ratio.\n"
    )
    tldr = "## TL;DR for Agents\n**Retrieved by:** [[skills/cac/]]\n**Answers:** \"q\"\n**Key facts:** facts\n"
    out = mod.insert_tldr_after_title(full, tldr)
    # Original title still present
    assert "# LCR" in out
    # TL;DR appears AFTER the title and BEFORE the original Summary
    pos_title = out.index("# LCR")
    pos_tldr = out.index("## TL;DR for Agents")
    pos_summary = out.index("## Summary")
    assert pos_title < pos_tldr < pos_summary


def test_insert_tldr_handles_no_title_heading(mod):
    full = "---\ntype: concept\n---\n\nJust some body text.\n"
    tldr = "## TL;DR for Agents\n**Retrieved by:** [[skills/cac/]]\n**Answers:** \"q\"\n**Key facts:** facts"
    out = mod.insert_tldr_after_title(full, tldr)
    # TL;DR placed at start of body when no title
    assert out.startswith("---\ntype: concept\n---\n\n## TL;DR for Agents")


def test_checkpoint_roundtrip(mod, tmp_path: Path):
    p = tmp_path / "ckpt.json"
    assert mod.load_checkpoint(p) == set()
    mod.save_checkpoint(p, {"a/b.md", "c/d.md"})
    again = mod.load_checkpoint(p)
    assert again == {"a/b.md", "c/d.md"}


def test_checkpoint_handles_corrupt_file(mod, tmp_path: Path):
    p = tmp_path / "ckpt.json"
    p.write_text("not json")
    assert mod.load_checkpoint(p) == set()


@pytest.mark.asyncio
async def test_draft_tldr_with_mock_llm(mod, tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cac" / "concepts").mkdir(parents=True)
    note = vault / "cac" / "concepts" / "lcr.md"
    note.write_text(
        "---\ntype: concept\ndepartment: cac\n---\n\n"
        "# LCR\n\n## Summary\nLiquidity Coverage Ratio measures HQLA / outflows.\n",
        encoding="utf-8",
    )

    async def fake_llm(prompt: str) -> str:
        # Verify the prompt has the expected pieces, then return a valid TL;DR
        assert "## TL;DR for Agents" in prompt  # prompt schema present
        assert "Liquidity Coverage Ratio" in prompt  # body included
        return (
            "## TL;DR for Agents\n"
            "**Retrieved by:** [[skills/cac/liquidity-analysis]]\n"
            "**Answers:** \"What is the LCR?\"\n"
            "**Key facts:** LCR = HQLA / 30-day net outflows; floor 100% per Basel III.\n"
        )

    item = mod.BackfillItem(rel_path="cac/concepts/lcr.md", codes={"tldr"})
    out = await mod.draft_tldr(llm=fake_llm, item=item, vault_root=vault)
    assert out is not None
    assert out.startswith("## TL;DR for Agents")
    assert "**Retrieved by:**" in out
    assert "**Answers:**" in out
    assert "**Key facts:**" in out


@pytest.mark.asyncio
async def test_draft_tldr_skips_when_already_present(mod, tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cac" / "concepts").mkdir(parents=True)
    note = vault / "cac" / "concepts" / "lcr.md"
    note.write_text(
        "---\ntype: concept\n---\n\n# LCR\n\n## TL;DR for Agents\nalready there\n",
        encoding="utf-8",
    )
    called = []
    async def llm(p):
        called.append(p)
        return "..."
    item = mod.BackfillItem(rel_path="cac/concepts/lcr.md", codes={"tldr"})
    out = await mod.draft_tldr(llm=llm, item=item, vault_root=vault)
    assert out is None
    assert called == []  # LLM not invoked


@pytest.mark.asyncio
async def test_draft_tldr_strips_code_fence(mod, tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cac" / "concepts").mkdir(parents=True)
    (vault / "cac" / "concepts" / "lcr.md").write_text(
        "---\ntype: concept\n---\n\n# LCR\n\n## Summary\nx.\n",
        encoding="utf-8",
    )
    async def llm(p):
        return (
            "```markdown\n"
            "## TL;DR for Agents\n"
            "**Retrieved by:** [[skills/cac/x]]\n"
            "**Answers:** \"q?\"\n"
            "**Key facts:** facts.\n"
            "```\n"
        )
    item = mod.BackfillItem(rel_path="cac/concepts/lcr.md", codes={"tldr"})
    out = await mod.draft_tldr(llm=llm, item=item, vault_root=vault)
    assert out is not None
    assert out.startswith("## TL;DR for Agents")
    assert "```" not in out


@pytest.mark.asyncio
async def test_draft_tldr_salvages_when_heading_missing(mod, tmp_path: Path):
    """If the LLM forgets to include the `## TL;DR for Agents` heading
    but does emit the three bullet lines, the script reconstructs the heading."""
    vault = tmp_path / "vault"
    (vault / "cac" / "concepts").mkdir(parents=True)
    (vault / "cac" / "concepts" / "lcr.md").write_text(
        "---\ntype: concept\n---\n\n# LCR\n\n## Summary\nx.\n",
        encoding="utf-8",
    )
    async def llm(p):
        return "**Retrieved by:** [[skills/cac/x]]\n**Answers:** \"q?\"\n**Key facts:** facts.\n"
    item = mod.BackfillItem(rel_path="cac/concepts/lcr.md", codes={"tldr"})
    out = await mod.draft_tldr(llm=llm, item=item, vault_root=vault)
    assert out is not None
    assert out.startswith("## TL;DR for Agents")
