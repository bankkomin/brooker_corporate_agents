"""Test that all SKILL.md files parse valid YAML frontmatter."""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills"


def get_skill_files():
    """Collect all .md files with YAML frontmatter."""
    files = []
    for f in SKILL_DIR.rglob("*.md"):
        if f.name.startswith("_") or "template" in str(f) or "history" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        if text.startswith("---"):
            files.append(f)
    return files


@pytest.mark.parametrize("skill_file", get_skill_files(), ids=lambda f: str(f.relative_to(SKILL_DIR)))
def test_frontmatter_parses(skill_file):
    text = skill_file.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert m, f"No frontmatter found in {skill_file}"
    fm = yaml.safe_load(m.group(1))
    assert isinstance(fm, dict), f"Frontmatter is not a dict in {skill_file}"
    assert "name" in fm, f"Missing 'name' in frontmatter of {skill_file}"
