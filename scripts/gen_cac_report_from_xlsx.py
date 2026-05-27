"""Produce a CAC meeting report FIRST DRAFT (.docx) from a filled Data Pack.

Thin CLI over services/shared/cac_report_docx.py (the same deterministic builder
deck-writer uses for the Slack pipeline). Reads a filled CAC_Monthly_Data_Pack.xlsx
— or pulls it straight from a SharePoint/OneDrive sharing link via MS Graph — and
writes the populated CFO-report .docx. Figures come straight from the cells (no
RAG, no LLM, no fabrication); only limit-status flags + a deterministic summary
are added.

Usage:
    # from a local file
    python scripts/gen_cac_report_from_xlsx.py --xlsx data/reports/pack.xlsx \
        --out data/reports/CAC_Report_May_2026.docx --month "May 2026"

    # straight from a SharePoint/OneDrive share link (fetches via MS Graph)
    python scripts/gen_cac_report_from_xlsx.py --share-url "<url>" --month "May 2026"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, ".")  # so `services.shared` resolves when run from repo root
from services.shared.cac_report_docx import (  # noqa: E402
    build_cac_report_docx,
    pack_from_xlsx,
)


def main() -> int:
    try:  # ensure unicode (≥, –) prints on Windows cp1252 consoles
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--xlsx", default=None, help="local filled data pack .xlsx")
    ap.add_argument("--share-url", default=None,
                    help="SharePoint/OneDrive sharing link (fetched via MS Graph)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--month", default=date.today().strftime("%B %Y"))
    args = ap.parse_args()

    if args.share_url:
        sys.path.insert(0, "scripts")
        from fetch_share_xlsx import fetch  # loads MS_GRAPH from .env
        xlsx = Path("data/reports/_shared_pack.xlsx")
        asyncio.run(fetch(args.share_url, xlsx))
    elif args.xlsx:
        xlsx = Path(args.xlsx)
    else:
        ap.error("provide --xlsx <file> or --share-url <link>")

    out = Path(args.out or f"data/reports/CAC_Report_{args.month.replace(' ', '_')}.docx")
    pack = pack_from_xlsx(xlsx)
    breaches = build_cac_report_docx(pack, out, args.month)
    print(f"[report] wrote {out}  ({len(breaches)} flag(s))")
    for c in breaches:
        print(f"   ! {c['status']:6} {c['metric']}: {c['value']} (limit {c['limit']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
