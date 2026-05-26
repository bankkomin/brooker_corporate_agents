#!/usr/bin/env python3
"""Vault convention audit — per-note backfill TODO generator.

Scans `obsidian-vault/` and reports each concept / decision / regulation
note that is missing one of the wiki conventions introduced in
buckets A3 / B1 / B2:

  - missing `## TL;DR for Agents` section (B2)
  - eligible for `event_date` frontmatter (B1) — date in title, etc.
  - missing inline `(as of YYYY-MM, ...)` recency markers (A3) on
    notes in research/, regulations/, macro/

Output is a single markdown TODO file grouped by department, sortable
by user as they tick items off. No LLM, no rewrites — pure disk scan.

Usage:
    python scripts/vault_convention_audit.py
    python scripts/vault_convention_audit.py --out docs/backlog.md
    python scripts/vault_convention_audit.py --vault path/to/vault
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterator

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VAULT = ROOT / "obsidian-vault"
DEFAULT_OUT = ROOT / "docs" / "vault-convention-backfill-todo.md"

TLDR_RE = re.compile(r"^##\s+TL;DR\s+for\s+Agents\s*$", re.MULTILINE)
RECENCY_MARKER_RE = re.compile(r"\(as of \d{4}-\d{2}(?:-\d{2})?,\s*[^)]+\)")
DATE_IN_FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
RECENCY_REQUIRED_DEPTS = {"research", "regulations", "macro"}
RESERVED_FILE_NAMES = {"log.md", "lint-report.md", "index.md"}
EXCLUDED_DIRS = {"_memory", ".obsidian", "health-reports", "templates", "skills"}


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return ({}, text)
    end = text.find("\n---\n", 4)
    if end == -1:
        return ({}, text)
    try:
        fm = yaml.safe_load(text[4:end]) or {}
        if not isinstance(fm, dict):
            return ({}, text[end + 5:])
        return (fm, text[end + 5:])
    except yaml.YAMLError:
        return ({}, text[end + 5:])


def _iter_notes(vault_root: Path) -> Iterator[Path]:
    for path in vault_root.rglob("*.md"):
        if path.name in RESERVED_FILE_NAMES:
            continue
        parts = set(path.relative_to(vault_root).parts)
        if parts & EXCLUDED_DIRS:
            continue
        yield path


def audit_note(vault_root: Path, path: Path) -> list[str]:
    """Return a list of TODO codes for this note (empty if nothing to do)."""
    rel = path.relative_to(vault_root).as_posix()
    parts = rel.split("/")
    if len(parts) < 3:
        return []
    dept = parts[0]
    subfolder = parts[1]
    if subfolder not in {"concepts", "decisions", "entities", "trends"}:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    fm, body = _parse_frontmatter(text)
    ntype = str(fm.get("type", "")).lower()

    todos = []

    # B2 — TL;DR for Agents (concept/decision only)
    if ntype in {"concept", "decision", "decision_log"}:
        if not TLDR_RE.search(body):
            todos.append("tldr")

    # B1 — event_date opportunity. Heuristic: filename starts with YYYY-MM-DD
    # and frontmatter has no event_date yet. Decisions are the main case.
    if not str(fm.get("event_date", "")).strip():
        if DATE_IN_FILENAME_RE.match(path.name) and ntype in {"decision", "decision_log"}:
            todos.append("event_date")

    # A3 — recency markers in research/regulations/macro concepts
    if dept in RECENCY_REQUIRED_DEPTS and ntype == "concept":
        # Crude proxy for "has load-bearing claims": body has numbers or % or "as of"
        if re.search(r"\d+(\.\d+)?\s*%|\bBt\s*\d|\$\s*\d", body):
            if not RECENCY_MARKER_RE.search(body):
                todos.append("recency_marker")
    return todos


def audit_vault(vault_root: Path) -> dict[str, dict[str, list[tuple[str, list[str]]]]]:
    """Returns {dept: {subfolder: [(path, [todo_codes]), ...]}}"""
    out: dict[str, dict[str, list[tuple[str, list[str]]]]] = defaultdict(lambda: defaultdict(list))
    for path in _iter_notes(vault_root):
        todos = audit_note(vault_root, path)
        if not todos:
            continue
        rel = path.relative_to(vault_root).as_posix()
        dept, subfolder = rel.split("/", 2)[0], rel.split("/", 2)[1]
        out[dept][subfolder].append((rel, todos))
    return out


def render_report(vault_root: Path, audit: dict, today: date) -> str:
    total = sum(
        len(notes) for subs in audit.values() for notes in subs.values()
    )
    by_code = defaultdict(int)
    for subs in audit.values():
        for notes in subs.values():
            for _, codes in notes:
                for c in codes:
                    by_code[c] += 1

    lines = [
        f"# Vault Convention Backfill TODO",
        "",
        f"_Generated {today.isoformat()} by `scripts/vault_convention_audit.py`._",
        "",
        f"**Vault:** `{vault_root.as_posix()}`",
        f"**Notes needing backfill:** {total}",
        "",
        "## Summary by convention",
        "",
        f"- **`tldr`** — missing `## TL;DR for Agents` section (per B2): {by_code['tldr']}",
        f"- **`event_date`** — frontmatter `event_date` missing on dated decision (per B1): {by_code['event_date']}",
        f"- **`recency_marker`** — research/regulations/macro concept with quantitative claims but no `(as of YYYY-MM, ...)` marker (per A3): {by_code['recency_marker']}",
        "",
        "## How to use this list",
        "",
        "1. Pick a dept block below. The TODO list is per-note; multiple codes on one note mean multiple things to add.",
        "2. Edit the note in Obsidian. The relevant convention spec is in `obsidian-vault/templates/concept.md` (Recency Markers, Bi-Temporal Dates, TL;DR for Agents sections).",
        "3. Re-run this script after a backfill session to see the updated count.",
        "4. The script is fully idempotent — safe to re-run any time.",
        "",
        "## Backlog",
        "",
    ]
    for dept in sorted(audit.keys()):
        subs = audit[dept]
        dept_total = sum(len(notes) for notes in subs.values())
        lines.append(f"### {dept} *({dept_total} notes)*")
        for subfolder in sorted(subs.keys()):
            notes = sorted(subs[subfolder])
            lines.append(f"")
            lines.append(f"**{subfolder}/** ({len(notes)})")
            for rel, codes in notes:
                badge = " ".join(f"`{c}`" for c in codes)
                lines.append(f"- [ ] `{rel}` — {badge}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default=str(DEFAULT_VAULT),
                    help=f"Vault path (default: {DEFAULT_VAULT})")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help=f"Output path (default: {DEFAULT_OUT})")
    args = ap.parse_args()

    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        print(f"ERROR: vault not found at {vault}", file=sys.stderr)
        return 2

    audit = audit_vault(vault)
    report = render_report(vault, audit, date.today())

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    total = sum(len(notes) for subs in audit.values() for notes in subs.values())
    print(f"Audited {sum(1 for _ in _iter_notes(vault))} notes; {total} need backfill.")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
