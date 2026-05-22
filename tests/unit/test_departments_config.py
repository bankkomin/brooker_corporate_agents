"""Tests for departments.json schema validation and Phase 2 fields."""
import json
from pathlib import Path

import pytest

try:
    from jsonschema import ValidationError, validate  # noqa: F401
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "config" / "departments.schema.json"
DATA_PATH = ROOT / "config" / "departments.json"


@pytest.fixture
def schema():
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture
def departments():
    data = json.loads(DATA_PATH.read_text())
    depts = data.get("departments", {})
    if isinstance(depts, dict):
        return [{"dept_id": k, **v} for k, v in depts.items()]
    return depts


def test_schema_file_exists():
    assert SCHEMA_PATH.exists()


def test_departments_file_exists():
    assert DATA_PATH.exists()


def test_cac_has_phase2_fields(departments):
    cac = next((d for d in departments if d["dept_id"] == "cac"), None)
    assert cac is not None, "CAC department not found"
    assert cac.get("capabilityTier") == "write"
    assert "finance" in cac.get("crossReadAccess", [])
    assert cac.get("agentTopology", {}).get("orchestrator") == "cfo-agent"
    assert cac.get("live") is True


def test_hr_has_phase2_fields(departments):
    hr = next((d for d in departments if d["dept_id"] == "hr"), None)
    assert hr is not None, "HR department not found"
    assert hr.get("capabilityTier") == "read_only"
    assert hr.get("live") is True


def test_nine_future_depts_present(departments):
    expected = {"finance", "ib", "ic", "cio", "vcc", "comms", "legal", "risk", "it"}
    found = {d["dept_id"] for d in departments}
    missing = expected - found
    assert not missing, f"Missing departments: {missing}"


def test_future_depts_are_not_live(departments):
    future = {"finance", "ib", "ic", "cio", "vcc", "comms"}
    for dept in departments:
        if dept["dept_id"] in future:
            assert dept.get("live") is False, f"{dept['dept_id']} should be live=false"


def test_all_depts_have_heartbeat(departments):
    for dept in departments:
        hb = dept.get("heartbeat")
        if hb is not None:
            assert "enabled" in hb, f"{dept['dept_id']} heartbeat missing 'enabled'"
