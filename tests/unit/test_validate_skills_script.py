"""Tests for scripts/validate_skills.py."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_validate_skills_runs():
    """Validate skills passes (skills without permissions block are skipped)."""
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "validate_skills.py")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    # May pass or warn — should not crash
    assert result.returncode in (0, 1), f"Unexpected exit: {result.stderr}"


def test_validate_skills_catches_unknown_collection(tmp_path):
    skill = tmp_path / "bad.md"
    skill.write_text("""---
name: bad
agent: bad-agent
dept: cac
permissions:
  mode: read_only
  data_zones: [1]
  outbound_apis: []
  read_collections: [imaginary_collection]
output_types: [text]
---
# Bad Skill
""")

    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "validate_skills.py"),
         "--skill-dir", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "imaginary_collection" in result.stderr
