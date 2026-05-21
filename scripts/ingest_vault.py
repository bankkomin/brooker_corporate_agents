"""One-time backfill of the Obsidian vault into Qdrant per config/obsidian_watch.json.

The vault watcher (services/rag-ingestion/src/vault_watcher.py) is live-only — it
catches new edits but never scans the ~648 existing files. This script does that
initial scan: it reads the watch-folder → collection/doc_type map and uploads each
markdown file to rag-ingestion's /ingest/document, so every department agent can
retrieve its own wiki (concepts, decisions, entities, meeting-notes, trends).
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

INGEST_URL = "http://localhost:3004/ingest/document"
VAULT = Path("obsidian-vault")
CONFIG = Path("config/obsidian_watch.json")


async def ingest_one(client, sem, path: Path, *, dept, doc_type, collection, retries=3):
    async with sem:
        for attempt in range(1, retries + 1):
            try:
                with path.open("rb") as fh:
                    files = {"file": (path.name, fh.read(), "text/markdown")}
                # doc_type MUST be the file extractor ("md"); the article type
                # (concept/decision_log/entity/...) goes in `category` metadata.
                data = {"dept": dept.upper(), "doc_type": "md",
                        "collection": collection, "category": doc_type,
                        "source": "obsidian_vault"}
                r = await client.post(INGEST_URL, files=files, data=data, timeout=120)
                if r.status_code != 200:
                    raise RuntimeError(f"http_{r.status_code}:{r.text[:120]}")
                body = r.json()
                if body.get("status") == "ingested":
                    return ("ok", body.get("chunks", 0))
                return ("skip", body.get("reason", "no_chunks"))
            except Exception as e:  # noqa: BLE001
                if attempt == retries:
                    return ("err", str(e)[:120])
                await asyncio.sleep(2 ** attempt)
    return ("err", "exhausted")


async def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    ignore_files = set(cfg.get("ignore_files", []))
    ignore_dirs = set(cfg.get("ignore_folders", []))

    # Build (file, dept, doc_type, collection) work list from the watch map.
    work: list[tuple[Path, str, str, str]] = []
    for entry in cfg["watch_folders"]:
        rel = entry["path"].strip("/")
        dept = rel.split("/")[0]
        folder = VAULT / rel
        if not folder.exists():
            continue
        for f in folder.rglob("*.md"):
            if f.name in ignore_files:
                continue
            if any(part in ignore_dirs for part in f.parts):
                continue
            work.append((f, dept, entry["doc_type"], entry["collection"]))

    print(f"[vault] {len(work)} markdown files to ingest", flush=True)
    sem = asyncio.Semaphore(3)
    ok = skip = err = chunks = 0
    by_coll: dict[str, int] = {}
    start = time.monotonic()
    async with httpx.AsyncClient() as client:
        tasks = [asyncio.create_task(
            ingest_one(client, sem, f, dept=d, doc_type=dt, collection=c))
            for (f, d, dt, c) in work]
        colls = [c for (_, _, _, c) in work]
        for i, fut in enumerate(asyncio.as_completed(tasks), 1):
            status, detail = await fut
            if status == "ok":
                ok += 1
                chunks += int(detail or 0)
            elif status == "skip":
                skip += 1
            else:
                err += 1
            if i % 50 == 0 or i == len(work):
                rate = i / (time.monotonic() - start)
                print(f"  [{i}/{len(work)}] ok={ok} skip={skip} err={err} "
                      f"chunks={chunks} · {rate:.1f}/s", flush=True)
    print(f"\n[vault] DONE ok={ok} skip={skip} err={err} chunks={chunks} "
          f"wall={(time.monotonic()-start):.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
