# services/rag-ingestion/src/vault_reingest.py
"""Dept-scoped bulk vault re-ingestion logic.

This module contains the VaultReingester class that powers POST /reingest-vault.
It is intentionally separated from main.py so it can be unit-tested without
standing up the full FastAPI application.

Design notes
------------
- Files are processed sequentially (one at a time) to avoid hammering the
  embedding service, which runs on a single shared vLLM process.
- Streaming output uses newline-delimited JSON so callers can consume progress
  in real time without waiting for the full corpus to finish.
- The 'source' metadata field is set to the vault-relative path
  (e.g. "obsidian-vault/ib/entities/foo.md") on every chunk.  This is the
  field used by delete_by_source_prefix() when delete_stale=True.
- The 'source_file' field (set by the chunker) will contain the absolute temp
  file path, which is less useful for prefix-based deletion.  This divergence
  is a pre-existing design issue — see PRE-EXISTING BUGS section in main.py.
"""
from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from .chunker import DocumentChunker
from .embedder import Embedder
from .models import ReIngestVaultResult
from .qdrant_store import QdrantStore

logger = structlog.get_logger("rag-ingestion.vault_reingest")

# Daily-log files older than this many days are skipped during bulk reingest.
# Vault-watchers still pick these up when they are first created; this cutoff
# only applies to the retroactive reingest path.
DAILY_LOG_MAX_AGE_DAYS = 90


class VaultReingester:
    """Performs a dept-scoped bulk re-ingest of the Obsidian vault."""

    def __init__(
        self,
        chunker: DocumentChunker,
        embedder: Embedder,
        store: QdrantStore,
        vault_root: Path,
        watch_config: dict[str, Any],
    ) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._vault_root = vault_root  # e.g. Path("/mnt/obsidian-vault")
        self._watch_config = watch_config

    # ── Public streaming entry-point ──────────────────────────────────────

    async def reingest_streaming(
        self,
        dept: str,
        subdirs: list[str] | None,
        delete_stale: bool,
        dry_run: bool,
    ) -> AsyncIterator[str]:
        """Yield newline-delimited JSON progress events.

        Yields:
            {"event":"start","dept":"ib","total_files":16}
            {"event":"file","name":"...","chunks":3,"collection":"ib_knowledge","status":"ok"}
            ...
            {"event":"done","files":16,"chunks":97,"deleted":0,"duration_s":38.4,"errors":[]}

        On dry_run=True yields:
            {"event":"start","dept":"ib","total_files":16,"dry_run":true}
            {"event":"file","name":"...","collection":"ib_knowledge","dry_run":true}
            ...
            {"event":"done","files":16,"dry_run":true,"duration_s":0.01,"errors":[]}
        """
        start_ts = time.monotonic()
        errors: list[str] = []

        entries = self._resolve_entries(dept, subdirs)
        file_list = self._collect_files(entries)

        yield _ndjson({"event": "start", "dept": dept, "total_files": len(file_list), "dry_run": dry_run})

        if dry_run:
            for file_path, collection, doc_type, _ in file_list:
                rel = self._vault_rel(file_path)
                yield _ndjson({"event": "file", "name": rel, "collection": collection, "doc_type": doc_type, "dry_run": True})
            elapsed = time.monotonic() - start_ts
            yield _ndjson({
                "event": "done",
                "files": len(file_list),
                "dry_run": True,
                "duration_s": round(elapsed, 3),
                "errors": errors,
            })
            return

        # ── delete_stale: wipe existing chunks before processing ──────────
        chunks_deleted = 0
        if delete_stale:
            affected_collections = {c for _, c, _, _ in file_list}
            source_prefix = f"obsidian-vault/{dept}/"
            for coll in affected_collections:
                try:
                    n = await self._store.delete_by_source_prefix(coll, source_prefix)
                    chunks_deleted += n
                    logger.info(
                        "vault_reingest.stale_deleted",
                        collection=coll,
                        prefix=source_prefix,
                        count=n,
                    )
                except Exception as exc:  # noqa: BLE001
                    msg = f"delete_stale failed on {coll}: {exc!s}"
                    errors.append(msg)
                    logger.error("vault_reingest.stale_delete_failed", collection=coll, error=str(exc))

        # ── sequential file ingest ─────────────────────────────────────────
        files_processed = 0
        chunks_created = 0
        collections_seen: set[str] = set()

        for file_path, collection, doc_type, dept_upper in file_list:
            rel = self._vault_rel(file_path)
            try:
                n_chunks = await self._ingest_file(
                    file_path=file_path,
                    collection=collection,
                    doc_type=doc_type,
                    dept=dept_upper,
                    vault_rel=rel,
                )
                files_processed += 1
                chunks_created += n_chunks
                collections_seen.add(collection)
                yield _ndjson({
                    "event": "file",
                    "name": rel,
                    "chunks": n_chunks,
                    "collection": collection,
                    "doc_type": doc_type,
                    "status": "ok" if n_chunks > 0 else "skipped",
                })
                logger.info(
                    "vault_reingest.file_done",
                    file=rel,
                    collection=collection,
                    chunks=n_chunks,
                )
            except Exception as exc:  # noqa: BLE001
                msg = f"{rel}: {exc!s}"
                errors.append(msg)
                files_processed += 1  # count as processed (attempted)
                logger.error("vault_reingest.file_error", file=rel, error=str(exc))
                yield _ndjson({
                    "event": "file",
                    "name": rel,
                    "chunks": 0,
                    "collection": collection,
                    "doc_type": doc_type,
                    "status": "error",
                    "error": str(exc)[:200],
                })

        elapsed = time.monotonic() - start_ts
        yield _ndjson({
            "event": "done",
            "dept": dept,
            "files": files_processed,
            "chunks": chunks_created,
            "deleted": chunks_deleted,
            "collections": sorted(collections_seen),
            "duration_s": round(elapsed, 2),
            "errors": errors,
        })

    # ── Non-streaming summary (convenience wrapper) ────────────────────────

    async def reingest(
        self,
        dept: str,
        subdirs: list[str] | None,
        delete_stale: bool,
        dry_run: bool,
    ) -> ReIngestVaultResult:
        """Consume the streaming generator and return a final summary."""
        start_ts = time.monotonic()
        files_processed = 0
        chunks_created = 0
        chunks_deleted = 0
        collections_seen: set[str] = set()
        errors: list[str] = []
        files_found: list[str] = []

        async for line in self.reingest_streaming(dept, subdirs, delete_stale, dry_run):
            event = json.loads(line)
            if event["event"] == "file":
                if dry_run:
                    files_found.append(event["name"])
                else:
                    files_processed += 1
                    chunks_created += event.get("chunks", 0)
                    collections_seen.add(event["collection"])
                    if event.get("status") == "error":
                        errors.append(event.get("error", event["name"]))
            elif event["event"] == "done":
                chunks_deleted = event.get("deleted", 0)

        return ReIngestVaultResult(
            dept=dept,
            files_processed=files_processed if not dry_run else len(files_found),
            chunks_created=chunks_created,
            chunks_deleted=chunks_deleted,
            collections_affected=sorted(collections_seen),
            duration_seconds=round(time.monotonic() - start_ts, 2),
            errors=errors,
            dry_run=dry_run,
            files_found=files_found,
        )

    # ── Internal helpers ───────────────────────────────────────────────────

    def _resolve_entries(
        self,
        dept: str,
        subdirs: list[str] | None,
    ) -> list[dict[str, str]]:
        """Return watch_folders entries for *dept*, optionally filtered by subdirs."""
        entries = []
        for entry in self._watch_config.get("watch_folders", []):
            path_str = entry["path"].strip("/")
            first_seg = path_str.split("/")[0]
            if first_seg != dept:
                continue
            if subdirs is not None:
                # e.g. path "ib/entities/" → second segment "entities"
                parts = path_str.split("/")
                subdir_seg = parts[1] if len(parts) > 1 else ""
                if subdir_seg not in subdirs:
                    continue
            entries.append(entry)
        return entries

    def _collect_files(
        self,
        entries: list[dict[str, str]],
    ) -> list[tuple[Path, str, str, str]]:
        """Walk all entries, apply ignore rules, return (path, collection, doc_type, dept_upper)."""
        ignore_files: set[str] = set(self._watch_config.get("ignore_files", []))
        ignore_dirs: set[str] = set(self._watch_config.get("ignore_folders", []))
        now = datetime.now(UTC)
        result: list[tuple[Path, str, str, str]] = []
        seen: set[Path] = set()

        for entry in entries:
            rel = entry["path"].strip("/")
            dept_upper = rel.split("/")[0].upper()
            subdir_slug = rel.split("/")[1] if "/" in rel else rel
            folder = self._vault_root / rel
            if not folder.exists():
                logger.debug("vault_reingest.folder_missing", folder=str(folder))
                continue

            for file_path in sorted(folder.rglob("*.md")):
                if file_path in seen:
                    continue
                # ignore dotfiles
                if any(part.startswith(".") for part in file_path.parts):
                    continue
                # ignore configured dirs
                if any(part in ignore_dirs for part in file_path.parts):
                    continue
                # ignore configured filenames
                if file_path.name in ignore_files:
                    continue
                # daily-log age cutoff
                if subdir_slug == "daily-logs" and not self._is_recent_enough(file_path, now):
                    logger.debug("vault_reingest.daily_log_stale_skipped", file=str(file_path))
                    continue
                seen.add(file_path)
                result.append((file_path, entry["collection"], entry["doc_type"], dept_upper))

        return result

    def _is_recent_enough(self, path: Path, now: datetime) -> bool:
        """Return True if a daily-log file should be ingested (not older than DAILY_LOG_MAX_AGE_DAYS)."""
        try:
            # Daily-log filenames are conventionally YYYY-MM-DD.md
            date_str = path.stem  # "2026-04-15"
            dt = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
            age_days = (now - dt).days
            return age_days <= DAILY_LOG_MAX_AGE_DAYS
        except ValueError:
            # Non-standard filename — don't skip it
            return True

    def _vault_rel(self, file_path: Path) -> str:
        """Return vault-relative path using forward slashes, e.g. 'obsidian-vault/ib/entities/foo.md'."""
        try:
            # vault_root is e.g. /mnt/obsidian-vault; rel starts from its parent
            # so the returned path looks like "obsidian-vault/ib/..."
            vault_parent = self._vault_root.parent
            rel = file_path.relative_to(vault_parent)
            return str(rel).replace("\\", "/")
        except ValueError:
            return str(file_path).replace("\\", "/")

    async def _ingest_file(
        self,
        *,
        file_path: Path,
        collection: str,
        doc_type: str,
        dept: str,
        vault_rel: str,
    ) -> int:
        """Chunk, embed, and upsert a single vault file.  Returns chunk count."""
        extra_meta: dict[str, str] = {
            "source": vault_rel,
            "source_type": "obsidian_vault",
            "category": doc_type,
        }
        chunks = await self._chunker.chunk_file(
            file_path,
            doc_type="md",
            dept=dept,
            extra_meta=extra_meta,
        )
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        vectors = await self._embedder.embed_texts(texts)
        count = await self._store.upsert_chunks(
            collection=collection,
            texts=texts,
            vectors=vectors,
            metadatas=metadatas,
        )
        return count


def _ndjson(obj: dict[str, Any]) -> str:
    """Serialise *obj* as a single JSON line (no trailing newline — caller adds it)."""
    return json.dumps(obj, ensure_ascii=False)
