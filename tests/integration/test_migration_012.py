"""Integration tests for migration 012 — B4 synthesis tracker tables.

Verifies the SQL migration file is syntactically valid and contains
the expected schema elements. Full DB tests require a running Postgres
instance (gated by INTEGRATION_TESTS env var in apply_runner test).
"""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "012_synthesis_tracker.sql"


def test_migration_file_exists():
    assert MIGRATION.exists()


def test_migration_contains_required_tables():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "entity_mentions" in sql
    assert "synthesis_state" in sql


def test_migration_has_constraints():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "UNIQUE (entity, source_doc, chunk_id)" in sql
    assert "PRIMARY KEY (entity, dept)" in sql
    # entity_kind CHECK constraint protects against typos
    assert "entity_kind IN" in sql
    # synthesis_state.status CHECK
    assert "status IN" in sql


def test_migration_has_required_indexes():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "idx_entity_mentions_entity_dept" in sql
    assert "idx_entity_mentions_dept_mentioned" in sql


def test_migration_uses_if_not_exists_for_idempotency():
    """Re-running the migration must be a no-op."""
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists entity_mentions" in sql
    assert "create table if not exists synthesis_state" in sql
    assert "create index if not exists" in sql


@pytest.mark.skipif(
    os.getenv("INTEGRATION_TESTS") != "1",
    reason="Set INTEGRATION_TESTS=1 to run against a real Postgres",
)
def test_migration_runner_applies_012_to_real_db(tmp_path: Path):
    """End-to-end: run scripts/apply_pending_migrations.py against a real
    Postgres and verify schema_migrations has the 012 row.

    Requires POSTGRES_DSN to be set. Idempotent — safe to run repeatedly.
    """
    import subprocess
    import psycopg2

    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN not set")

    script = ROOT / "scripts" / "apply_pending_migrations.py"
    result = subprocess.run(
        ["python", str(script), "--dsn", dsn],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"runner failed: {result.stderr}"

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filename FROM schema_migrations WHERE filename = %s",
                ("012_synthesis_tracker.sql",),
            )
            row = cur.fetchone()
        assert row is not None
        # And the tracked tables exist
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('entity_mentions'), to_regclass('synthesis_state')"
            )
            em, ss = cur.fetchone()
        assert em == "entity_mentions"
        assert ss == "synthesis_state"
    finally:
        conn.close()
