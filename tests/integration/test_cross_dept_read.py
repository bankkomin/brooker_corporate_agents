"""Integration tests for cross-department read access enforcement.

Tests verify config-level cross-read rules are correctly defined.
Full Qdrant tests require running infrastructure.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def dept_configs():
    data = json.loads((ROOT / "config" / "departments.json").read_text())
    depts = data.get("departments", {})
    if isinstance(depts, dict):
        return {k: {**v, "dept_id": k} for k, v in depts.items()}
    return {d["dept_id"]: d for d in depts}


def test_cac_can_read_finance(dept_configs):
    cac = dept_configs.get("cac", {})
    assert "finance" in cac.get("crossReadAccess", [])


def test_cac_can_read_risk(dept_configs):
    cac = dept_configs.get("cac", {})
    assert "risk" in cac.get("crossReadAccess", [])


def test_hr_cannot_read_finance(dept_configs):
    hr = dept_configs.get("hr", {})
    assert "finance" not in hr.get("crossReadAccess", [])


def test_legal_reads_all(dept_configs):
    legal = dept_configs.get("legal", {})
    assert "*" in legal.get("crossReadAccess", [])


def test_ic_reads_finance_cio_vcc_legal(dept_configs):
    ic = dept_configs.get("ic", {})
    cross = ic.get("crossReadAccess", [])
    for dept in ["finance", "cio", "vcc", "legal"]:
        assert dept in cross, f"IC should read {dept}"


def test_risk_reads_cac_cio_finance_legal(dept_configs):
    risk = dept_configs.get("risk", {})
    cross = risk.get("crossReadAccess", [])
    for dept in ["cac", "cio", "finance", "legal"]:
        assert dept in cross, f"Risk should read {dept}"


def test_isolated_depts_have_no_crossread(dept_configs):
    for dept_id in ["hr", "comms", "it"]:
        dept = dept_configs.get(dept_id, {})
        cross = dept.get("crossReadAccess", [])
        assert cross == [], f"{dept_id} should have empty crossReadAccess, got {cross}"
