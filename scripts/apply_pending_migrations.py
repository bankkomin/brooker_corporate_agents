#!/usr/bin/env python3
"""Apply any pending SQL migrations to a running Postgres.

Existing Postgres deployments don't auto-run new SQL files (the
docker-compose `/docker-entrypoint-initdb.d` mount only fires on first
init of an empty data volume). This script fills that gap: it tracks
applied migrations in a `schema_migrations` table and runs every .sql
file under `migrations/` that hasn't been applied yet, in lexical order.

Idempotent: re-running it is a no-op if nothing is pending.

Usage:
    POSTGRES_DSN="postgresql://user:pass@host:5432/db" \\
        python scripts/apply_pending_migrations.py

    # Or use the same vars Docker Compose passes:
    python scripts/apply_pending_migrations.py \\
        --host postgres --port 5432 --db corporate_agents \\
        --user agents --password changeme

    # Dry run — print what would happen, don't execute:
    python scripts/apply_pending_migrations.py --dry-run

Exit codes:
    0 = success (including "nothing to apply")
    1 = at least one migration failed (transaction rolled back)
    2 = connection / config error
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2 import sql as psql
except ImportError:  # pragma: no cover
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "migrations"

SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sha256 TEXT NOT NULL
);
"""


def _hash_file(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def discover_migrations(migrations_dir: Path) -> list[Path]:
    """All *.sql files in lexical order."""
    if not migrations_dir.is_dir():
        return []
    return sorted(p for p in migrations_dir.glob("*.sql") if p.is_file())


def already_applied(conn, migrations: list[Path]) -> dict[str, str]:
    """Return {filename: sha256} for migrations already in schema_migrations."""
    with conn.cursor() as cur:
        cur.execute("SELECT filename, sha256 FROM schema_migrations")
        return dict(cur.fetchall())


def apply_one(conn, migration: Path, *, dry_run: bool = False) -> None:
    """Run one migration's SQL inside an autocommit-off transaction."""
    sql_text = migration.read_text(encoding="utf-8")
    sha = _hash_file(migration)
    print(f"  applying {migration.name} (sha256={sha[:12]}...)")
    if dry_run:
        return
    with conn.cursor() as cur:
        cur.execute(sql_text)
        cur.execute(
            "INSERT INTO schema_migrations (filename, sha256) VALUES (%s, %s) "
            "ON CONFLICT (filename) DO UPDATE SET sha256 = EXCLUDED.sha256, applied_at = NOW()",
            (migration.name, sha),
        )
    conn.commit()


def build_dsn(args: argparse.Namespace) -> str:
    if args.dsn:
        return args.dsn
    if env := os.getenv("POSTGRES_DSN"):
        return env
    return (
        f"host={args.host} port={args.port} dbname={args.db} "
        f"user={args.user} password={args.password}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dsn", default=None, help="Full DSN (or set POSTGRES_DSN env var)")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=5432)
    ap.add_argument("--db", default="corporate_agents")
    ap.add_argument("--user", default="agents")
    ap.add_argument("--password", default="changeme")
    ap.add_argument("--migrations-dir", default=str(MIGRATIONS_DIR))
    ap.add_argument("--dry-run", action="store_true", help="Show pending; don't execute")
    args = ap.parse_args()

    migrations_dir = Path(args.migrations_dir)
    migrations = discover_migrations(migrations_dir)
    if not migrations:
        print(f"No migrations found in {migrations_dir}")
        return 0

    dsn = build_dsn(args)
    try:
        conn = psycopg2.connect(dsn)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: cannot connect to Postgres: {exc}", file=sys.stderr)
        return 2

    try:
        # Ensure tracking table exists. Run outside any other transaction.
        with conn.cursor() as cur:
            cur.execute(SCHEMA_MIGRATIONS_DDL)
        conn.commit()

        applied = already_applied(conn, migrations)
        pending: list[Path] = []
        for m in migrations:
            if m.name in applied:
                # Optional: warn if sha drifted (someone edited an applied migration)
                current_sha = _hash_file(m)
                if applied[m.name] != current_sha:
                    print(
                        f"  WARN: {m.name} was applied but sha256 changed "
                        f"(stored {applied[m.name][:12]}, now {current_sha[:12]}). "
                        "Edits to applied migrations are not re-run; create a follow-up migration."
                    )
                continue
            pending.append(m)

        if not pending:
            print(f"All {len(migrations)} migration(s) already applied. Nothing to do.")
            return 0

        print(f"Found {len(pending)} pending migration(s):")
        failed: list[str] = []
        for m in pending:
            try:
                apply_one(conn, m, dry_run=args.dry_run)
            except Exception as exc:
                conn.rollback()
                print(f"  FAILED {m.name}: {exc}", file=sys.stderr)
                failed.append(m.name)
                # Stop on first failure so order is preserved
                break

        if failed:
            return 1
        action = "Would apply" if args.dry_run else "Applied"
        print(f"{action} {len(pending)} migration(s).")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
