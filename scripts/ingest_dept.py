"""Targeted vault ingestion for specific departments.

Usage:
    python scripts/ingest_dept.py ib ic
    python scripts/ingest_dept.py ib --dry-run
    python scripts/ingest_dept.py ib --delete-stale
    python scripts/ingest_dept.py ib --subdirs entities concepts

Hits POST /reingest-vault on the rag-ingestion service, consuming the
newline-delimited JSON progress stream and printing each event as it
arrives.  The old per-file loop has been replaced by this single call.

CLI args are intentionally kept identical to the previous version so
existing callers (scripts, cron jobs, CI) do not need changes.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys

import httpx

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

REINGEST_URL = "http://localhost:3004/reingest-vault"


async def reingest_dept(
    dept: str,
    *,
    subdirs: list[str] | None = None,
    delete_stale: bool = False,
    dry_run: bool = False,
) -> int:
    """Call /reingest-vault and stream progress to stdout.

    Returns 0 on success, 1 if any errors were reported.
    """
    payload: dict = {"dept": dept, "delete_stale": delete_stale, "dry_run": dry_run}
    if subdirs:
        payload["subdirs"] = subdirs

    errors_seen: list[str] = []

    async with (
        httpx.AsyncClient(timeout=None) as client,
        client.stream("POST", REINGEST_URL, json=payload) as resp,
    ):
        if resp.status_code != 200:
            body = await resp.aread()
            print(
                f"[ingest_dept] ERROR {resp.status_code}: {body.decode(errors='replace')[:300]}",
                flush=True,
            )
            return 1

        async for raw_line in resp.aiter_lines():
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                print(f"  [warn] non-JSON line: {raw_line[:120]}", flush=True)
                continue

            ev = event.get("event")
            if ev == "start":
                prefix = "[dry-run] " if event.get("dry_run") else ""
                print(
                    f"[ingest_dept] {prefix}dept={dept} total_files={event.get('total_files', '?')}",
                    flush=True,
                )
            elif ev == "file":
                if event.get("dry_run"):
                    print(
                        f"  WOULD  {event.get('name')}  coll={event.get('collection')}",
                        flush=True,
                    )
                else:
                    status = event.get("status", "ok")
                    if status == "error":
                        print(
                            f"  ERR    {event.get('name')}  {event.get('error', '')[:120]}",
                            flush=True,
                        )
                        errors_seen.append(event.get("name", "?"))
                    elif status == "skipped":
                        print(
                            f"  SKIP   {event.get('name')}  chunks=0",
                            flush=True,
                        )
                    else:
                        print(
                            f"  OK     {event.get('name')}  "
                            f"chunks={event.get('chunks', 0)}  coll={event.get('collection')}",
                            flush=True,
                        )
            elif ev == "done":
                if event.get("dry_run"):
                    print(
                        f"\n[ingest_dept] DRY-RUN DONE  files_found={event.get('files', 0)}"
                        f"  duration_s={event.get('duration_s', 0):.1f}",
                        flush=True,
                    )
                else:
                    print(
                        f"\n[ingest_dept] DONE"
                        f"  files={event.get('files', 0)}"
                        f"  chunks={event.get('chunks', 0)}"
                        f"  deleted={event.get('deleted', 0)}"
                        f"  errors={len(event.get('errors', []))}"
                        f"  duration_s={event.get('duration_s', 0):.1f}",
                        flush=True,
                    )
                    errs = event.get("errors", [])
                    if errs:
                        print("[ingest_dept] Errors:", flush=True)
                        for e in errs:
                            print(f"  {e}", flush=True)
                    colls = event.get("collections", [])
                    if colls:
                        print("[ingest_dept] Collections written:", flush=True)
                        for c in colls:
                            print(f"  {c}", flush=True)
                    errors_seen.extend(errs)

    return 1 if errors_seen else 0


async def main(depts: list[str], *, subdirs: list[str] | None, delete_stale: bool, dry_run: bool) -> int:
    exit_code = 0
    for dept in depts:
        rc = await reingest_dept(
            dept,
            subdirs=subdirs,
            delete_stale=delete_stale,
            dry_run=dry_run,
        )
        if rc != 0:
            exit_code = rc
    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-ingest one or more dept vaults via /reingest-vault")
    parser.add_argument("depts", nargs="*", default=["ib"], metavar="DEPT", help="Dept slug(s) to re-ingest")
    parser.add_argument("--subdirs", nargs="*", metavar="SUBDIR", help="Restrict to specific subdirs (e.g. entities concepts)")
    parser.add_argument("--delete-stale", action="store_true", help="Delete existing chunks before re-ingesting")
    parser.add_argument("--dry-run", action="store_true", help="List files without ingesting")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(
        args.depts,
        subdirs=args.subdirs,
        delete_stale=args.delete_stale,
        dry_run=args.dry_run,
    )))
