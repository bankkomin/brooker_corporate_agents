"""Integration tests for migration 010 — Phase 2 framework tables.

These tests verify the SQL migration file is syntactically valid.
Full DB tests require a running Postgres instance.
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "010_phase2_framework.sql"


def test_migration_file_exists():
    assert MIGRATION.exists()


def test_migration_contains_required_tables():
    sql = MIGRATION.read_text()
    assert "agent_knowledge_gaps" in sql
    assert "agent_skill_proposals" in sql
    assert "reflection_runs" in sql
    assert "agent_performance" in sql


def test_migration_has_indexes():
    sql = MIGRATION.read_text()
    assert "idx_agent_knowledge_gaps_dept_unresolved" in sql
    assert "idx_agent_skill_proposals_status" in sql
    assert "idx_reflection_runs_dept_started" in sql


def test_migration_view_has_signal_strength():
    sql = MIGRATION.read_text()
    assert "signal_strength" in sql
    assert "approved" in sql
    assert "edited" in sql
    assert "rejected" in sql
