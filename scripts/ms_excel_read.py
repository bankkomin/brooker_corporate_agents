"""CLI to read Excel Online via MS Graph (uses services/shared/ms_graph_excel).

Loads MS_GRAPH_* from .env, then:
  --list                 list files in the user's OneDrive (root or --folder)
  --path FILE [--sheet]  read a workbook's used range and print it

Examples:
  python scripts/ms_excel_read.py --list
  python scripts/ms_excel_read.py --path "ALCO_Tracker.xlsx"
  python scripts/ms_excel_read.py --path "Treasury/ALCO.xlsx" --user cfo@brookergroup.com
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# load .env into os.environ (no python-dotenv dependency)
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line.startswith("MS_GRAPH_") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k] = v.strip().strip('"')

sys.path.insert(0, ".")
from services.shared.ms_graph_excel import GraphExcel  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--folder", default="root")
    ap.add_argument("--path")
    ap.add_argument("--sheet")
    ap.add_argument("--user")
    args = ap.parse_args()

    gx = GraphExcel.from_env()
    if args.list:
        items = await gx.list_children(args.folder, user=args.user)
        print(f"{len(items)} item(s) in {args.user or os.environ.get('MS_GRAPH_SENDER_EMAIL')} /{args.folder}:")
        for it in items:
            kind = "DIR " if it.get("folder") else "file"
            print(f"  {kind} {it.get('name')}")
        return 0
    if args.path:
        data = await gx.read_workbook_by_path(args.path, user=args.user, sheet=args.sheet)
        for sheet, rows in data.items():
            print(f"\n=== {sheet} ({len(rows)} rows) ===")
            for row in rows[:15]:
                print("  ", [str(c)[:20] for c in row])
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
