"""Download a SharePoint/OneDrive sharing link to a local .xlsx via MS Graph.

Resolves the sharing URL → drive item → workbook used range (read-only) and
rebuilds a local .xlsx so other tools (e.g. gen_cac_report_from_xlsx.py) can
consume it with openpyxl. Auth uses the MS_GRAPH_* client-credentials app.

Usage:
    python scripts/fetch_share_xlsx.py "<share_url>" -o data/reports/pack.xlsx
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, ".")


def _load_env() -> None:
    """Load MS_GRAPH_* from .env into os.environ (no python-dotenv dependency)."""
    for line in Path(".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("MS_GRAPH_") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k] = v.strip().strip('"')


async def fetch(share_url: str, out: Path) -> dict[str, list[list]]:
    _load_env()
    from services.shared.ms_graph_excel import GraphExcel
    gx = GraphExcel.from_env()
    data = await gx.read_workbook_by_share_url(share_url)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet, rows in data.items():
        ws = wb.create_sheet(title=sheet[:31])
        for row in rows:
            ws.append(list(row))
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("share_url")
    ap.add_argument("-o", "--out", default="data/reports/_shared_pack.xlsx")
    args = ap.parse_args()

    out = Path(args.out)
    data = asyncio.run(fetch(args.share_url, out))
    print(f"[fetch] wrote {out}")
    for sheet, rows in data.items():
        print(f"   - {sheet}: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
