#!/usr/bin/env python3
"""Mirror skills/<dept>/*.md → obsidian-vault/skills/<dept>/*.md.

The agent runtime reads SKILL.md files from `skills/<dept>/`. Per the project
convention (see CAC and HR examples), those same files are mirrored into
`obsidian-vault/skills/<dept>/` so they appear in Obsidian alongside the
concepts/decisions/entities/etc.

This script keeps the wiki copy byte-equal to the runtime copy. It is one-way:
`skills/` is the source of truth; vault copies are derived. Run before commit
or as a pre-deploy step.

Usage:
    python scripts/sync_skills_to_vault.py            # sync + report
    python scripts/sync_skills_to_vault.py --check    # exit 1 if out of sync
    python scripts/sync_skills_to_vault.py --dept ic  # restrict to one dept
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
VAULT_SKILLS_ROOT = REPO_ROOT / "obsidian-vault" / "skills"


def sync_dept(dept_dir: Path, *, check_only: bool = False) -> tuple[int, int, int]:
    """Sync one department directory.

    Returns (copied, unchanged, drift_detected).
    In check mode, copied is always 0 and drift_detected counts how many files
    would have been copied or removed.
    """
    dept = dept_dir.name
    target_dir = VAULT_SKILLS_ROOT / dept
    target_dir.mkdir(parents=True, exist_ok=True)

    src_files = {p.name for p in dept_dir.glob("*.md")}
    dst_files = {p.name for p in target_dir.glob("*.md")}

    copied = unchanged = drift = 0

    # Files in source: copy if missing or different
    for name in sorted(src_files):
        src = dept_dir / name
        dst = target_dir / name
        if dst.exists() and filecmp.cmp(src, dst, shallow=False):
            unchanged += 1
            continue
        if check_only:
            drift += 1
            print(f"  DRIFT  {dept}/{name}  (would copy)")
        else:
            shutil.copy2(src, dst)
            copied += 1
            print(f"  COPY   {dept}/{name}")

    # Files in target but not source: warn (do not delete — could be unrelated)
    for name in sorted(dst_files - src_files):
        print(f"  ORPHAN {dept}/{name}  (in vault but not in skills/{dept}/)")
        drift += 1

    return copied, unchanged, drift


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="Verify only; exit 1 on drift")
    parser.add_argument("--dept", help="Restrict to one department")
    args = parser.parse_args()

    if not SKILLS_ROOT.is_dir():
        print(f"ERROR: skills root not found at {SKILLS_ROOT}", file=sys.stderr)
        return 2

    dept_dirs = sorted(p for p in SKILLS_ROOT.iterdir() if p.is_dir())
    if args.dept:
        dept_dirs = [p for p in dept_dirs if p.name == args.dept]
        if not dept_dirs:
            print(f"ERROR: dept '{args.dept}' not found in {SKILLS_ROOT}", file=sys.stderr)
            return 2

    total_copied = total_unchanged = total_drift = 0
    print(f"{'CHECKING' if args.check else 'SYNCING'} {len(dept_dirs)} dept(s) "
          f"from {SKILLS_ROOT.relative_to(REPO_ROOT)} -> "
          f"{VAULT_SKILLS_ROOT.relative_to(REPO_ROOT)}")
    print()

    for dept_dir in dept_dirs:
        copied, unchanged, drift = sync_dept(dept_dir, check_only=args.check)
        total_copied += copied
        total_unchanged += unchanged
        total_drift += drift

    print()
    print(f"Summary: copied={total_copied}  unchanged={total_unchanged}  drift={total_drift}")

    if args.check and total_drift > 0:
        print("CHECK FAILED — run without --check to sync.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
