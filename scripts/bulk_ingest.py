"""Bulk-ingest a folder tree (or a list of paths) into rag-ingestion.

Replaces scripts/replay-ingest.sh. The bash version uses curl on Git Bash for
Windows, which silently drops requests when the filename contains Unicode
characters — every Thai-named POST returns an empty body before the server
sees it. This Python uploader uses httpx, which encodes multipart filenames
correctly per RFC 7578.

Features:
- Concurrency cap (asyncio.Semaphore, default 2)
- Exponential backoff retry on transient errors (default 3 attempts)
- Resume from a checkpoint file (one path per line, ok|skip|err prefix)
- Per-batch progress logging (every 25 files)
- Reads files from one of three sources:
    --from-paths FILE      : a text file with one absolute path per line
    --root DIR             : walk DIR recursively for ingestible files
    --from-errlog FILE     : extract paths from an ingest-bulk errors.log

Usage:
    python scripts/bulk_ingest.py --root "//192.168.1.33/digital asset/2nd_Brain/Thai_SEC_regulations" \
        --dept SHARED --collection shared_policies --source thai_sec_ocr
    python scripts/bulk_ingest.py --from-errlog /tmp/ingest-bulk/errors.log
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

# Force stdout to UTF-8 with replacement on Windows. Without this, printing a
# Thai filename to a cp1252 console crashes the worker (looks like an upload
# failure but the file may have ingested fine).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


def _safe(s: object) -> str:
    """Render any path/string safely for the current stdout encoding."""
    enc = (getattr(sys.stdout, "encoding", "") or "utf-8").lower()
    text = str(s)
    if enc == "utf-8":
        return text
    return text.encode(enc, errors="replace").decode(enc, errors="replace")

INGEST_URL = os.getenv("RAG_INGESTION_URL", "http://localhost:3004").rstrip("/") + "/ingest/document"

EXTENSION_MAP = {
    ".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx", ".pptx": "pptx",
    ".doc": "doc", ".xls": "xls", ".msg": "msg", ".md": "md", ".txt": "txt",
}
BLACKLIST = {
    ".js", ".css", ".gif", ".png", ".jpg", ".jpeg", ".db", ".ico",
    ".json", ".xml", ".woff", ".woff2", ".ttf", ".eot", ".svg",
    ".tmp", ".bak",
}


def detect_type(path: Path) -> str | None:
    return EXTENSION_MAP.get(path.suffix.lower())


def classify(path: Path) -> tuple[str, str, str] | None:
    """Map a file path to (dept, collection, source) based on its location.
    Mirrors the original run.sh classification: brooker_database/{dept}/*
    goes to {dept}_docs; 2nd_Brain/* goes to shared_policies."""
    s = str(path).replace("\\", "/")
    if "/brooker_database/" in s:
        m = re.search(r"/brooker_database/([^/]+)/", s)
        if m:
            dept = m.group(1)
            return (dept, f"{dept}_docs", "brooker_database")
    if "/2nd_Brain/" in s:
        return ("shared", "shared_policies", "2nd_brain")
    return None


async def ingest_one(client: httpx.AsyncClient, sem: asyncio.Semaphore,
                     path: Path, *, dept: str, collection: str, source: str,
                     timeout: float, retries: int) -> tuple[str, str]:
    """Returns (status, detail). status in {ok, skip, err}."""
    if path.suffix.lower() in BLACKLIST:
        return ("skip", "blacklisted_ext")
    doc_type = detect_type(path)
    if not doc_type:
        return ("skip", f"unsupported_ext:{path.suffix}")
    if not path.is_file():
        return ("err", "not_a_file")

    async with sem:
        last_err = ""
        for attempt in range(1, retries + 1):
            try:
                with path.open("rb") as fh:
                    files = {
                        "file": (path.name, fh.read(), "application/octet-stream"),
                    }
                data = {
                    "dept": dept.upper(),
                    "doc_type": doc_type,
                    "collection": collection,
                    "source": source,
                }
                r = await client.post(INGEST_URL, files=files, data=data,
                                       timeout=timeout)
                if r.status_code != 200:
                    last_err = f"http_{r.status_code}:{r.text[:120]}"
                    raise RuntimeError(last_err)
                body = r.json()
                status = body.get("status")
                if status == "ingested":
                    return ("ok", f"chunks={body.get('chunks', 0)}")
                if status == "skipped":
                    return ("skip", body.get("reason") or "no_chunks_extracted")
                return ("err", body.get("reason") or f"status:{status}")
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last_err = f"{type(e).__name__}:{e}"
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}:{e}"
                break
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)  # 2s, 4s, 8s
        return ("err", last_err or "exhausted_retries")


def collect_paths(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    if args.root:
        root = Path(args.root)
        for p in root.rglob("*"):
            if p.is_file():
                paths.append(p)
    if args.from_paths:
        for line in Path(args.from_paths).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                paths.append(Path(line))
    if args.from_errlog:
        # errors.log line shape: "ERR  /path/to/file :: ...."
        # also accepts bare "/path/to/file".
        for line in Path(args.from_errlog).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ERR "):
                line = line[4:].split(" ::", 1)[0].strip()
            if line and "/" in line:
                paths.append(Path(line))
    # Deduplicate, preserve order.
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def load_checkpoint(path: str | None) -> set[str]:
    if not path or not os.path.exists(path):
        return set()
    done: set[str] = set()
    for line in open(path, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) == 2:
            done.add(parts[1])
    return done


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_argument_group("source")
    src.add_argument("--root", help="recursively walk this folder")
    src.add_argument("--from-paths", help="text file with one path per line")
    src.add_argument("--from-errlog", help="ingest-bulk errors.log to retry")
    ap.add_argument("--dept", default="SHARED",
                     help="dept tag for ingestion. ignored if classifier finds one.")
    ap.add_argument("--collection", default="shared_policies",
                     help="qdrant collection. ignored if classifier finds one.")
    ap.add_argument("--source", default="bulk_ingest",
                     help="source string stored in metadata")
    ap.add_argument("--auto-classify", action="store_true",
                     help="route brooker_database/{dept}/* to {dept}_docs and 2nd_Brain/* to shared_policies (auto)")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=600.0)
    ap.add_argument("--checkpoint", help="resume file: one '<status>\\t<path>' per line")
    ap.add_argument("--limit", type=int, default=0, help="cap total files; 0=unbounded")
    args = ap.parse_args()

    if not (args.root or args.from_paths or args.from_errlog):
        ap.error("specify --root, --from-paths, or --from-errlog")

    paths = collect_paths(args)
    if args.limit:
        paths = paths[: args.limit]
    done = load_checkpoint(args.checkpoint)
    todo = [p for p in paths if str(p) not in done]
    print(f"[bulk_ingest] {len(paths)} candidates · {len(done)} already done · {len(todo)} to process",
          flush=True)

    ckpt_fh = open(args.checkpoint, "a", encoding="utf-8") if args.checkpoint else None
    sem = asyncio.Semaphore(args.concurrency)
    ok = err = skip = 0
    start = time.monotonic()

    async with httpx.AsyncClient() as client:
        async def worker(path: Path):
            nonlocal ok, err, skip
            if args.auto_classify:
                cls = classify(path)
                if cls:
                    dept, collection, source = cls
                else:
                    dept, collection, source = args.dept, args.collection, args.source
            else:
                dept, collection, source = args.dept, args.collection, args.source
            status, detail = await ingest_one(
                client, sem, path,
                dept=dept, collection=collection, source=source,
                timeout=args.timeout, retries=args.retries,
            )
            if status == "ok":
                ok += 1
            elif status == "skip":
                skip += 1
            else:
                err += 1
            if ckpt_fh:
                ckpt_fh.write(f"{status}\t{path}\n")
                ckpt_fh.flush()
            return (status, path, detail)

        tasks = [asyncio.create_task(worker(p)) for p in todo]
        for i, fut in enumerate(asyncio.as_completed(tasks), start=1):
            try:
                status, path, detail = await fut
                if status == "err":
                    print(f"  ERR  {_safe(path)} :: {_safe(detail)[:120]}", flush=True)
            except Exception as e:  # noqa: BLE001
                err += 1
                print(f"  ERR  (task crash) :: {_safe(e)}", flush=True)
            if i % 25 == 0 or i == len(todo):
                elapsed = time.monotonic() - start
                rate = i / elapsed if elapsed else 0
                eta = (len(todo) - i) / rate if rate else 0
                print(f"  [{time.strftime('%H:%M:%S')}] {i}/{len(todo)} "
                      f"ok={ok} err={err} skip={skip} · {rate:.1f}/s · ETA {eta/60:.1f}min",
                      flush=True)

    if ckpt_fh:
        ckpt_fh.close()
    print(f"\n[bulk_ingest] DONE ok={ok} err={err} skip={skip} "
          f"wall={time.monotonic()-start:.1f}s", flush=True)
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
