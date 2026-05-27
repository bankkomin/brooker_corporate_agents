"""Unit tests for scripts/apply_pending_migrations.py (logic only — no real DB)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "apply_pending_migrations.py"


@pytest.fixture
def runner_module():
    """Import the script as a module so we can unit-test its functions."""
    spec = importlib.util.spec_from_file_location("apply_pending_migrations", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["apply_pending_migrations"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_exists():
    assert SCRIPT.is_file()


def test_help_runs_without_error():
    """The CLI shouldn't crash on --help."""
    result = subprocess.run(
        ["python", str(SCRIPT), "--help"], capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    assert "Apply any pending SQL migrations" in result.stdout


def test_discover_migrations_returns_sorted(tmp_path: Path, runner_module):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "002_b.sql").write_text("-- b")
    (mig_dir / "001_a.sql").write_text("-- a")
    (mig_dir / "010_c.sql").write_text("-- c")
    (mig_dir / "readme.txt").write_text("ignored")  # non-sql
    out = runner_module.discover_migrations(mig_dir)
    assert [p.name for p in out] == ["001_a.sql", "002_b.sql", "010_c.sql"]


def test_discover_migrations_missing_dir_returns_empty(tmp_path: Path, runner_module):
    assert runner_module.discover_migrations(tmp_path / "nope") == []


def test_hash_file_is_deterministic(tmp_path: Path, runner_module):
    f = tmp_path / "x.sql"
    f.write_text("CREATE TABLE x (id int);")
    assert runner_module._hash_file(f) == runner_module._hash_file(f)


def test_build_dsn_prefers_explicit_dsn(runner_module):
    import argparse
    ns = argparse.Namespace(
        dsn="postgresql://explicit", host="h", port=1, db="d", user="u", password="p",
    )
    assert runner_module.build_dsn(ns) == "postgresql://explicit"


def test_build_dsn_falls_back_to_kv(runner_module):
    import argparse
    ns = argparse.Namespace(
        dsn=None, host="h", port=5432, db="d", user="u", password="p",
    )
    # Strip POSTGRES_DSN env to test fallback path
    import os
    prev = os.environ.pop("POSTGRES_DSN", None)
    try:
        dsn = runner_module.build_dsn(ns)
        assert "host=h" in dsn
        assert "dbname=d" in dsn
        assert "user=u" in dsn
    finally:
        if prev is not None:
            os.environ["POSTGRES_DSN"] = prev
