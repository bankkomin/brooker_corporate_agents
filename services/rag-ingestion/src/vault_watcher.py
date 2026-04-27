# services/rag-ingestion/src/vault_watcher.py
"""Obsidian vault watcher — monitors .md files, ingests into config-driven collections."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import structlog
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .chunker import DocumentChunker
from .config import RAGSettings
from .embedder import Embedder
from .qdrant_store import QdrantStore

logger = structlog.get_logger("rag-ingestion.vault_watcher")

KNOWLEDGE_COLLECTION = "cac_knowledge"


class VaultWatcher:
    """Watches an Obsidian vault directory for .md file changes."""

    def __init__(
        self,
        settings: RAGSettings,
        chunker: DocumentChunker,
        embedder: Embedder,
        store: QdrantStore,
        postgres_dsn: str,
    ) -> None:
        self._vault_path = settings.obsidian_vault_path
        self._debounce_seconds = settings.obsidian_ingest_delay_seconds
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._postgres_dsn = postgres_dsn
        self._observer: Observer | None = None
        self._pending: dict[str, asyncio.TimerHandle] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._watch_config = self._load_watch_config(settings)

    def _load_watch_config(self, settings: RAGSettings) -> dict[str, Any]:
        """Load obsidian_watch.json; return empty structure on failure."""
        config_path = getattr(settings, "obsidian_watch_config", "/app/config/obsidian_watch.json")
        try:
            with open(config_path) as f:
                return json.load(f)  # type: ignore[no-any-return]
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("vault_watcher.config_not_found", path=config_path, error=str(exc))
            return {"watch_folders": [], "ignore_folders": [], "ignore_files": []}

    def _resolve_collection_and_type(self, path_str: str) -> tuple[str, str, str]:
        """Return (collection, doc_type, dept) for a vault file path.

        Matches the file's vault-relative path against watch_folders entries.
        The dept is derived from the first path segment (e.g. "cac" → "CAC").
        Falls back to (KNOWLEDGE_COLLECTION, "md", "unknown") when no entry matches.
        """
        vault = Path(self._vault_path)
        try:
            rel = Path(path_str).relative_to(vault)
        except ValueError:
            return (KNOWLEDGE_COLLECTION, "md", "unknown")

        rel_str = str(rel).replace("\\", "/")  # normalise Windows paths

        for entry in self._watch_config.get("watch_folders", []):
            if rel_str.startswith(entry["path"]):
                dept = rel_str.split("/")[0].upper()
                return (entry["collection"], entry["doc_type"], dept)

        return (KNOWLEDGE_COLLECTION, "md", "unknown")

    def _should_ignore(self, path_str: str) -> bool:
        """Return True if the file should be skipped per watch config rules."""
        vault = Path(self._vault_path)
        try:
            rel = Path(path_str).relative_to(vault)
        except ValueError:
            return False

        rel_str = str(rel).replace("\\", "/")
        filename = Path(path_str).name

        for folder in self._watch_config.get("ignore_folders", []):
            # Match at the start or anywhere as a path component
            if rel_str.startswith(folder + "/") or ("/" + folder + "/") in rel_str:
                return True

        return filename in self._watch_config.get("ignore_files", [])

    async def start(self) -> None:
        """Start watching the vault directory."""
        vault = Path(self._vault_path)
        if not vault.exists():
            logger.warning("vault_watcher.path_missing", path=self._vault_path)
            return

        self._loop = asyncio.get_running_loop()
        handler = _VaultEventHandler(self._on_file_event)
        self._observer = Observer()
        self._observer.schedule(handler, str(vault), recursive=True)
        self._observer.start()
        logger.info("vault_watcher.started", path=self._vault_path)

    async def stop(self) -> None:
        """Stop watching."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        # Cancel pending debounce timers
        for handle in self._pending.values():
            handle.cancel()
        self._pending.clear()
        logger.info("vault_watcher.stopped")

    def _on_file_event(self, path: str) -> None:
        """Called from watchdog thread — schedule debounced async processing."""
        if not path.endswith(".md"):
            return
        if self._loop is None:
            return
        if self._should_ignore(path):
            logger.debug("vault_watcher.ignored", path=path)
            return

        # Cancel existing timer for this file
        if path in self._pending:
            self._pending[path].cancel()

        # Schedule debounced processing
        handle = self._loop.call_later(
            self._debounce_seconds,
            lambda p=path: self._loop.create_task(self._process_file(p)) if self._loop else None,  # type: ignore[union-attr]
        )
        self._pending[path] = handle

    async def _process_file(self, path_str: str) -> None:
        """Process a single .md file: hash check, chunk, embed, upsert."""
        self._pending.pop(path_str, None)
        path = Path(path_str)

        if not path.exists():
            logger.debug("vault_watcher.file_gone", path=path_str)
            return

        collection, doc_type, dept = self._resolve_collection_and_type(path_str)
        file_hash = self._hash_file(path)

        # Dedup via ingested_documents table
        if await self._is_already_ingested(path_str, file_hash):
            logger.debug("vault_watcher.unchanged", path=path_str)
            return

        # Delete old vectors for this file
        await self._store.delete_by_file(collection, path_str)

        # Chunk and embed
        chunks = await self._chunker.chunk_file(path, doc_type=doc_type, dept=dept)
        if not chunks:
            return

        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        vectors = await self._embedder.embed_texts(texts)

        await self._store.upsert_chunks(
            collection=collection,
            texts=texts,
            vectors=vectors,
            metadatas=metadatas,
        )

        await self._record_ingestion(path_str, file_hash, len(chunks), dept=dept, doc_type=doc_type)
        logger.info(
            "vault_watcher.ingested",
            path=path_str,
            collection=collection,
            doc_type=doc_type,
            dept=dept,
            chunks=len(chunks),
        )

    async def _is_already_ingested(self, filename: str, file_hash: str) -> bool:
        """Check ingested_documents table for matching hash."""
        import psycopg2

        def _check() -> bool:
            conn = psycopg2.connect(self._postgres_dsn)
            cur = conn.cursor()
            cur.execute(
                "SELECT file_hash FROM ingested_documents"
                " WHERE filename = %s ORDER BY created_at DESC LIMIT 1",
                (filename,),
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row is not None and row[0] == file_hash

        try:
            return await asyncio.to_thread(_check)
        except Exception as exc:
            logger.error("vault_watcher.db_check_failed", error=str(exc))
            return False

    async def _record_ingestion(
        self,
        filename: str,
        file_hash: str,
        chunks: int,
        *,
        dept: str = "unknown",
        doc_type: str = "md",
    ) -> None:
        """Insert or update ingested_documents record."""
        import psycopg2

        def _record() -> None:
            conn = psycopg2.connect(self._postgres_dsn)
            cur = conn.cursor()
            # ON CONFLICT updates the mutable fields only.
            # created_at must NOT be updated — it records the original ingest time.
            # Overwriting it would make re-indexing look like first-time ingestion.
            cur.execute(
                "INSERT INTO ingested_documents"
                " (filename, dept, doc_type, chunks_count, file_hash)"
                " VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (file_hash) DO UPDATE"
                " SET filename = EXCLUDED.filename,"
                "     dept = EXCLUDED.dept,"
                "     doc_type = EXCLUDED.doc_type,"
                "     chunks_count = EXCLUDED.chunks_count",
                (filename, dept, doc_type, chunks, file_hash),
            )
            conn.commit()
            cur.close()
            conn.close()

        try:
            await asyncio.to_thread(_record)
        except Exception as exc:
            logger.error("vault_watcher.db_record_failed", error=str(exc))

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()


class _VaultEventHandler(FileSystemEventHandler):
    """Watchdog handler that forwards .md events."""

    def __init__(self, callback) -> None:  # noqa: ANN001
        self._callback = callback

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._callback(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._callback(event.src_path)
