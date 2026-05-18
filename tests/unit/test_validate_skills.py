import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "validate_skills.py"


def _run(skill_dir: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--skill-dir", str(skill_dir)],
        capture_output=True, text=True,
    )


def _write(path: Path, frontmatter: str, body: str = "Body."):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


def test_dangling_shared_skill_reference_fails(tmp_path):
    _write(tmp_path / "finance" / "reporting.md",
           "name: reporting-agent\npermissions:\n  mode: write_via_staging\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []\n"
           "shared_skills:\n  - shared/investment-cluster/missing")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "shared_skills" in result.stderr and "missing" in result.stderr


def test_resolved_shared_skill_reference_passes(tmp_path):
    _write(tmp_path / "shared" / "investment-cluster" / "valuation-methodology.md",
           "name: valuation-methodology\npermissions:\n  mode: read_only\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []")
    _write(tmp_path / "finance" / "reporting.md",
           "name: reporting-agent\npermissions:\n  mode: write_via_staging\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []\n"
           "shared_skills:\n  - shared/investment-cluster/valuation-methodology")
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr


def test_cluster_skill_must_be_read_only(tmp_path):
    _write(tmp_path / "shared" / "investment-cluster" / "bad.md",
           "name: bad\npermissions:\n  mode: write_via_staging\n"
           "  data_zones: [1]\n  outbound_apis: []\n  read_collections: []")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "read_only" in result.stderr


def test_cluster_skill_outbound_apis_must_be_empty(tmp_path):
    _write(tmp_path / "shared" / "investment-cluster" / "bad2.md",
           "name: bad2\npermissions:\n  mode: read_only\n"
           "  data_zones: [1]\n  outbound_apis: [gmail]\n  read_collections: []")
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "outbound_apis" in result.stderr
