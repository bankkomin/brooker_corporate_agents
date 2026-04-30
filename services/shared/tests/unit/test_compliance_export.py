"""Tests for services.shared.compliance_export — Phase 6.6 audit trail export."""
from __future__ import annotations

import json

import pytest

from services.shared.compliance_export import AuditEntry, _export_csv, _export_json


# --- Fixtures ---


@pytest.fixture()
def sample_entries() -> list[AuditEntry]:
    return [
        AuditEntry(
            timestamp="2026-04-01T10:00:00",
            dept_id="cac",
            event_type="query",
            actor="user-001",
            summary="Query: What is the current LCR?",
            details={"query": "What is the current LCR?", "response": "The current LCR is 135%.", "agent": "liquidity-agent"},
        ),
        AuditEntry(
            timestamp="2026-04-01T10:05:00",
            dept_id="cac",
            event_type="proposal",
            actor="liquidity-agent",
            summary="Proposed E8 = 3.15 (confidence: 91%)",
            details={"proposal_id": 42, "cell": "E8", "value": "3.15", "confidence": 0.91, "status": "pending"},
        ),
        AuditEntry(
            timestamp="2026-04-01T11:00:00",
            dept_id="cac",
            event_type="approved",
            actor="hod",
            summary="APPROVED: E8 = 3.15",
            details={"action": "approved", "cell": "E8"},
        ),
        AuditEntry(
            timestamp="2026-04-01T12:00:00",
            dept_id="cac",
            event_type="escalation",
            actor="system",
            summary="[high] LCR approaching regulatory minimum",
            details={"severity": "high", "reason": "LCR approaching regulatory minimum"},
        ),
    ]


# --- _export_json ---


def test_export_json_structure(sample_entries):
    result = _export_json(sample_entries)
    data = json.loads(result)

    assert isinstance(data, list)
    assert len(data) == 4


def test_export_json_fields(sample_entries):
    result = _export_json(sample_entries)
    data = json.loads(result)

    first = data[0]
    assert first["timestamp"] == "2026-04-01T10:00:00"
    assert first["dept_id"] == "cac"
    assert first["event_type"] == "query"
    assert first["actor"] == "user-001"
    assert "LCR" in first["summary"]
    assert "query" in first["details"]


def test_export_json_empty():
    result = _export_json([])
    data = json.loads(result)
    assert data == []


def test_export_json_is_valid_json(sample_entries):
    result = _export_json(sample_entries)
    # Should not raise
    parsed = json.loads(result)
    assert isinstance(parsed, list)


# --- _export_csv ---


def test_export_csv_header(sample_entries):
    result = _export_csv(sample_entries)
    lines = result.strip().split("\n")
    assert lines[0] == "timestamp,dept_id,event_type,actor,summary"


def test_export_csv_row_count(sample_entries):
    result = _export_csv(sample_entries)
    lines = result.strip().split("\n")
    # 1 header + 4 data rows
    assert len(lines) == 5


def test_export_csv_content(sample_entries):
    result = _export_csv(sample_entries)
    assert "2026-04-01T10:00:00" in result
    assert "cac" in result
    assert "user-001" in result


def test_export_csv_empty():
    result = _export_csv([])
    lines = result.strip().split("\n")
    assert len(lines) == 1  # header only
    assert "timestamp" in lines[0]


# --- AuditEntry dataclass ---


def test_audit_entry_creation():
    entry = AuditEntry(
        timestamp="2026-01-01T00:00:00",
        dept_id="treasury",
        event_type="query",
        actor="user-002",
        summary="Test query",
        details={"key": "value"},
    )
    assert entry.dept_id == "treasury"
    assert entry.details == {"key": "value"}
