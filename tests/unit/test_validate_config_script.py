"""Tests for scripts/validate_config.py."""
import subprocess
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_validate_config_passes_on_real_config():
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "validate_config.py")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_validate_config_fails_on_broken_inventory(tmp_path):
    # Create a minimal valid departments.json
    dept = tmp_path / "departments.json"
    dept.write_text(json.dumps({"version": "1.0", "departments": {}}))

    # Create departments schema
    schema = tmp_path / "departments.schema.json"
    schema.write_text(json.dumps({"type": "object"}))

    # Create broken inventory
    inv = tmp_path / "inv.json"
    inv.write_text(json.dumps({"documents": [
        {"id": "doc_finance_x", "title": "X", "ownerDept": "finance",
         "tier": "report", "vaultPath": "x", "qdrantCollection": "wrong_docs"}
    ]}))

    inv_schema = tmp_path / "inv_schema.json"
    inv_schema.write_text(json.dumps({
        "type": "object",
        "required": ["id", "title", "ownerDept", "tier", "vaultPath", "qdrantCollection"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "ownerDept": {"type": "string"},
            "tier": {"enum": ["policy", "report", "tracker", "narrative"]},
            "vaultPath": {"type": "string"},
            "qdrantCollection": {"type": "string"},
        }
    }))

    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "validate_config.py"),
         "--departments", str(dept),
         "--departments-schema", str(schema),
         "--inventory", str(inv),
         "--inventory-schema", str(inv_schema)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
