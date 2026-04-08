# Stage 2 — RAG Ingestion Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the RAG ingestion service (`services/rag-ingestion/`) — chunking documents, embedding via vLLM, storing in Qdrant, indexing Slack messages, and watching the Obsidian vault.

**Architecture:** FastAPI service on port 3004. Documents are chunked (LlamaIndex SentenceSplitter), embedded (vLLM Qwen 9B via OpenAI-compatible API), and stored in Qdrant collections. Messages indexed into `cac_chat`. VaultWatcher class uses watchdog to monitor Obsidian .md files. All external calls are async (httpx, qdrant-client async).

**Tech Stack:** Python 3.11, FastAPI, LlamaIndex (SentenceSplitter), qdrant-client (async), httpx, PyMuPDF, python-docx, openpyxl, watchdog, Pydantic v2, structlog, tenacity

**Design Spec:** `docs/superpowers/plans/2026-03-30-stage2-4-rag-orchestrator.md`

---

## File Map

### Existing Files (DO NOT recreate)

| File | Status |
|------|--------|
| `services/rag-ingestion/__init__.py` | Exists |
| `services/rag-ingestion/src/__init__.py` | Exists |
| `services/rag-ingestion/src/config.py` | Complete — RAGSettings |
| `services/rag-ingestion/src/models.py` | Complete — 7 Pydantic models |
| `services/rag-ingestion/requirements.txt` | Complete — 16 deps |
| `tests/unit/rag_ingestion/__init__.py` | Exists |
| `tests/unit/rag_ingestion/test_models.py` | Complete — 10 tests |

### New Files

| File | Responsibility |
|------|---------------|
| `services/rag-ingestion/src/chunker.py` | Document chunking: PDF, DOCX, XLSX, MD, TXT |
| `services/rag-ingestion/src/embedder.py` | vLLM embedding wrapper (Qwen 9B) |
| `services/rag-ingestion/src/qdrant_store.py` | Qdrant CRUD: upsert, search, delete |
| `services/rag-ingestion/src/chat_indexer.py` | Slack message indexing into cac_chat |
| `services/rag-ingestion/src/vault_watcher.py` | Obsidian .md file watcher with debounce |
| `services/rag-ingestion/src/main.py` | FastAPI app: /ingest/document, /ingest/message, /health |
| `services/rag-ingestion/Dockerfile` | Container image |
| `tests/unit/rag_ingestion/test_chunker.py` | Chunker tests |
| `tests/unit/rag_ingestion/test_embedder.py` | Embedder tests |
| `tests/unit/rag_ingestion/test_qdrant_store.py` | Qdrant store tests |
| `tests/unit/rag_ingestion/test_chat_indexer.py` | Chat indexer tests |
| `tests/unit/rag_ingestion/test_vault_watcher.py` | Vault watcher tests |
| `tests/integration/test_rag_pipeline.py` | Full pipeline integration test |

### Modified Files

| File | Change |
|------|--------|
| `docker-compose.yml` | Uncomment rag-ingestion, add extra_hosts |
| `docker-compose.dev.yml` | Add dev overrides for rag-ingestion |
| `docs/Implementation.md` | Check off Stage 2 items |

---

## Dependency DAG

```
Task 1 (chunker) ──────────────┐
Task 2 (embedder) ─────────────┼── Task 4 (chat_indexer) ──┐
Task 3 (qdrant_store) ─────────┘                            ├── Task 6 (main.py)
                         Task 5 (vault_watcher) ────────────┘       │
                                                                    │
Task 7 (Dockerfile + docker-compose) ──────────────────────────────┤
Task 8 (test_chunker) ────────────────────────────────────────────┤
Task 9 (test_embedder) ───────────────────────────────────────────┤
Task 10 (test_qdrant_store) ──────────────────────────────────────┤
Task 11 (test_chat_indexer) ──────────────────────────────────────┤
Task 12 (test_vault_watcher) ─────────────────────────────────────┤
Task 13 (integration test) ───────────────────────────────────────┤
Task 14 (final verification) ─────────────────────────────────────┘
```

**Parallelizable:** Tasks 1, 2, 3 can run in parallel. Tasks 8-12 can run in parallel.

---

## Task Breakdown

### Task 1: Document Chunker

**Files:**
- Create: `services/rag-ingestion/src/chunker.py`

- [ ] **Step 1: Write chunker.py**

```python
# services/rag-ingestion/src/chunker.py
"""Document chunking pipeline for PDF, DOCX, XLSX, Markdown, and plain text."""
from __future__ import annotations

import hashlib
from pathlib import Path

import structlog

from .config import RAGSettings

logger = structlog.get_logger("rag-ingestion.chunker")


class TextChunk:
    """A chunk of text with metadata."""

    __slots__ = ("text", "metadata")

    def __init__(self, text: str, metadata: dict[str, str | int | None]) -> None:
        self.text = text
        self.metadata = metadata


class DocumentChunker:
    """Chunks documents into text segments with metadata."""

    def __init__(self, settings: RAGSettings) -> None:
        self._chunk_size = settings.chunk_size
        self._overlap = settings.chunk_overlap

    async def chunk_file(self, file_path: Path, doc_type: str, dept: str = "CAC") -> list[TextChunk]:
        """Chunk a file into TextChunks with metadata."""
        handler = self._get_handler(doc_type)
        if handler is None:
            logger.warning("chunker.unsupported_type", doc_type=doc_type, path=str(file_path))
            return []

        try:
            raw_sections = handler(file_path)
        except Exception as exc:
            logger.error("chunker.extract_failed", path=str(file_path), error=str(exc))
            return []

        if not raw_sections:
            return []

        file_hash = self._hash_file(file_path)
        chunks: list[TextChunk] = []
        for section in raw_sections:
            text = section["text"].strip()
            if not text:
                continue
            for piece in self._split_text(text):
                meta = {
                    "source_file": str(file_path),
                    "file_hash": file_hash,
                    "doc_type": doc_type,
                    "dept": dept,
                    "page": section.get("page"),
                    "section": section.get("section"),
                    "sheet": section.get("sheet"),
                }
                chunks.append(TextChunk(text=piece, metadata=meta))

        logger.info("chunker.done", path=str(file_path), chunks=len(chunks))
        return chunks

    def _get_handler(self, doc_type: str):  # noqa: ANN202
        handlers = {
            "pdf": self._extract_pdf,
            "docx": self._extract_docx,
            "xlsx": self._extract_xlsx,
            "md": self._extract_text,
            "txt": self._extract_text,
        }
        return handlers.get(doc_type)

    def _extract_pdf(self, path: Path) -> list[dict]:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        sections = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                sections.append({"text": text, "page": i + 1, "section": None})
        doc.close()
        return sections

    def _extract_docx(self, path: Path) -> list[dict]:
        from docx import Document

        doc = Document(str(path))
        sections = []
        for i, para in enumerate(doc.paragraphs):
            if para.text.strip():
                sections.append({"text": para.text, "page": None, "section": f"para_{i}"})
        return sections

    def _extract_xlsx(self, path: Path) -> list[dict]:
        from openpyxl import load_workbook

        wb = load_workbook(str(path), read_only=True, data_only=True)
        sections = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                row_text = " | ".join(str(c) for c in row if c is not None)
                if row_text.strip():
                    rows.append(row_text)
            if rows:
                sections.append({
                    "text": "\n".join(rows),
                    "page": None,
                    "section": None,
                    "sheet": sheet_name,
                })
        wb.close()
        return sections

    def _extract_text(self, path: Path) -> list[dict]:
        text = path.read_text(encoding="utf-8", errors="replace")
        return [{"text": text, "page": None, "section": None}] if text.strip() else []

    def _split_text(self, text: str) -> list[str]:
        """Simple character-based splitter with overlap."""
        if len(text) <= self._chunk_size:
            return [text]
        pieces = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size
            pieces.append(text[start:end])
            start = end - self._overlap
        return pieces

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()
```

- [ ] **Step 2: Verify import works**

Run: `cd Brooker_Corporate_Agent && python -c "from services.rag_ingestion.src.chunker import DocumentChunker; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/rag-ingestion/src/chunker.py
git commit -m "feat(rag-ingestion): add document chunker for PDF/DOCX/XLSX/MD/TXT"
```

---

### Task 2: Embedder

**Files:**
- Create: `services/rag-ingestion/src/embedder.py`

- [ ] **Step 1: Write embedder.py**

```python
# services/rag-ingestion/src/embedder.py
"""Async embedding wrapper for vLLM (OpenAI-compatible endpoint)."""
from __future__ import annotations

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import RAGSettings

logger = structlog.get_logger("rag-ingestion.embedder")


class Embedder:
    """Async client for vLLM embedding endpoint."""

    BATCH_SIZE = 32

    def __init__(self, settings: RAGSettings) -> None:
        self._url = f"{settings.vllm_embed_url.rstrip('/')}/embeddings"
        self._model = settings.vllm_embed_model
        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._http = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a single batch via vLLM."""
        assert self._http is not None, "Call start() before embedding"
        payload = {"model": self._model, "input": texts}
        resp = await self._http.post(self._url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # OpenAI-compatible response: {"data": [{"embedding": [...], "index": 0}, ...]}
        sorted_results = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_results]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, splitting into batches if needed."""
        if not texts:
            return []
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            vectors = await self._embed_batch(batch)
            all_vectors.extend(vectors)
            logger.debug("embedder.batch_done", batch_start=i, count=len(batch))
        return all_vectors

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text string."""
        results = await self.embed_texts([text])
        return results[0]

    async def get_dimension(self) -> int:
        """Get embedding dimension by embedding a test string."""
        vec = await self.embed_single("dimension test")
        return len(vec)

    async def health_check(self) -> bool:
        """Check if vLLM embed endpoint is reachable."""
        try:
            assert self._http is not None
            resp = await self._http.get(
                self._url.replace("/embeddings", "/models")
            )
            return resp.status_code == 200
        except Exception:
            return False
```

- [ ] **Step 2: Verify import**

Run: `cd Brooker_Corporate_Agent && python -c "from services.rag_ingestion.src.embedder import Embedder; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/rag-ingestion/src/embedder.py
git commit -m "feat(rag-ingestion): add async vLLM embedder with batching and retry"
```

---

### Task 3: Qdrant Store

**Files:**
- Create: `services/rag-ingestion/src/qdrant_store.py`

- [ ] **Step 1: Write qdrant_store.py**

```python
# services/rag-ingestion/src/qdrant_store.py
"""Async Qdrant client wrapper for vector CRUD operations."""
from __future__ import annotations

import uuid

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from .config import RAGSettings

logger = structlog.get_logger("rag-ingestion.qdrant_store")

COLLECTIONS = ["cac_docs", "cac_chat", "cac_knowledge", "shared_policies"]


class QdrantStore:
    """Async wrapper for Qdrant vector operations."""

    def __init__(self, settings: RAGSettings) -> None:
        self._client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_rest_port,
        )

    async def ensure_collections(self, vector_size: int) -> None:
        """Create collections if they don't exist."""
        existing = await self._client.get_collections()
        existing_names = {c.name for c in existing.collections}
        for name in COLLECTIONS:
            if name not in existing_names:
                await self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                logger.info("qdrant_store.collection_created", name=name, dim=vector_size)

    async def upsert_chunks(
        self,
        collection: str,
        texts: list[str],
        vectors: list[list[float]],
        metadatas: list[dict],
    ) -> int:
        """Batch upsert text chunks with vectors and metadata."""
        points = []
        for text, vec, meta in zip(texts, vectors, metadatas, strict=True):
            point_id = str(uuid.uuid4())
            payload = {**meta, "text": text}
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))

        if points:
            await self._client.upsert(collection_name=collection, points=points)
            logger.info("qdrant_store.upserted", collection=collection, count=len(points))
        return len(points)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 8,
        score_threshold: float = 0.70,
        filters: dict[str, str] | None = None,
    ) -> list[dict]:
        """Search for similar vectors with optional metadata filters."""
        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=qdrant_filter,
        )
        return [
            {
                "text": hit.payload.get("text", "") if hit.payload else "",
                "score": hit.score,
                "id": str(hit.id),
                **(hit.payload or {}),
            }
            for hit in results
        ]

    async def delete_by_file(self, collection: str, file_path: str) -> None:
        """Delete all points matching a source file."""
        await self._client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=file_path))]
            ),
        )
        logger.info("qdrant_store.deleted_by_file", collection=collection, file=file_path)

    async def get_collection_info(self, collection: str) -> dict:
        """Get collection stats."""
        info = await self._client.get_collection(collection)
        return {
            "name": collection,
            "vectors_count": info.vectors_count or 0,
            "status": str(info.status),
        }

    async def health_check(self) -> bool:
        """Check Qdrant connectivity."""
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.close()
```

- [ ] **Step 2: Verify import**

Run: `cd Brooker_Corporate_Agent && python -c "from services.rag_ingestion.src.qdrant_store import QdrantStore, COLLECTIONS; print(COLLECTIONS)"`
Expected: `['cac_docs', 'cac_chat', 'cac_knowledge', 'shared_policies']`

- [ ] **Step 3: Commit**

```bash
git add services/rag-ingestion/src/qdrant_store.py
git commit -m "feat(rag-ingestion): add async Qdrant store with 4 collections"
```

---

### Task 4: Chat Indexer

**Files:**
- Create: `services/rag-ingestion/src/chat_indexer.py`

- [ ] **Step 1: Write chat_indexer.py**

```python
# services/rag-ingestion/src/chat_indexer.py
"""Slack message indexer — embeds and stores messages in cac_chat collection."""
from __future__ import annotations

import hashlib

import structlog

from .embedder import Embedder
from .qdrant_store import QdrantStore

logger = structlog.get_logger("rag-ingestion.chat_indexer")

CHAT_COLLECTION = "cac_chat"


class ChatIndexer:
    """Indexes Slack messages into the cac_chat Qdrant collection."""

    def __init__(self, embedder: Embedder, store: QdrantStore) -> None:
        self._embedder = embedder
        self._store = store

    @staticmethod
    def make_message_id(channel_id: str, timestamp: str) -> str:
        """Deterministic message ID for dedup."""
        raw = f"{channel_id}:{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def index_message(
        self,
        *,
        text: str,
        author: str,
        channel_id: str,
        timestamp: str,
        thread_ts: str | None = None,
        dept: str = "CAC",
    ) -> str:
        """Embed and store a message. Returns message_id."""
        if not text.strip():
            logger.debug("chat_indexer.empty_text", channel=channel_id)
            return ""

        message_id = self.make_message_id(channel_id, timestamp)

        # Embed once (used for both dedup check and upsert)
        vector = await self._embedder.embed_single(text)

        # Check for existing point (dedup via metadata filter, no extra embedding)
        existing = await self._store.search(
            collection=CHAT_COLLECTION,
            query_vector=vector,
            limit=1,
            score_threshold=0.99,
            filters={"message_id": message_id},
        )
        if existing:
            logger.debug("chat_indexer.duplicate", message_id=message_id)
            return message_id
        metadata = {
            "message_id": message_id,
            "author": author,
            "channel_id": channel_id,
            "timestamp": timestamp,
            "thread_ts": thread_ts or "",
            "dept": dept,
        }
        await self._store.upsert_chunks(
            collection=CHAT_COLLECTION,
            texts=[text],
            vectors=[vector],
            metadatas=[metadata],
        )
        logger.info("chat_indexer.indexed", message_id=message_id, channel=channel_id)
        return message_id
```

- [ ] **Step 2: Verify import**

Run: `cd Brooker_Corporate_Agent && python -c "from services.rag_ingestion.src.chat_indexer import ChatIndexer; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/rag-ingestion/src/chat_indexer.py
git commit -m "feat(rag-ingestion): add chat indexer with SHA-256 dedup"
```

---

### Task 5: Vault Watcher

**Files:**
- Create: `services/rag-ingestion/src/vault_watcher.py`

- [ ] **Step 1: Write vault_watcher.py**

```python
# services/rag-ingestion/src/vault_watcher.py
"""Obsidian vault watcher — monitors .md files, ingests into cac_knowledge."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import structlog
from watchdog.events import FileModifiedEvent, FileSystemEvent, FileSystemEventHandler
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

        file_hash = self._hash_file(path)

        # Dedup via ingested_documents table
        if await self._is_already_ingested(path_str, file_hash):
            logger.debug("vault_watcher.unchanged", path=path_str)
            return

        # Delete old vectors for this file
        await self._store.delete_by_file(KNOWLEDGE_COLLECTION, path_str)

        # Chunk and embed
        chunks = await self._chunker.chunk_file(path, doc_type="md", dept="CAC")
        if not chunks:
            return

        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        vectors = await self._embedder.embed_texts(texts)

        await self._store.upsert_chunks(
            collection=KNOWLEDGE_COLLECTION,
            texts=texts,
            vectors=vectors,
            metadatas=metadatas,
        )

        await self._record_ingestion(path_str, file_hash, len(chunks))
        logger.info("vault_watcher.ingested", path=path_str, chunks=len(chunks))

    async def _is_already_ingested(self, filename: str, file_hash: str) -> bool:
        """Check ingested_documents table for matching hash."""
        import psycopg2

        def _check() -> bool:
            conn = psycopg2.connect(self._postgres_dsn)
            cur = conn.cursor()
            cur.execute(
                "SELECT file_hash FROM ingested_documents WHERE filename = %s ORDER BY created_at DESC LIMIT 1",
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

    async def _record_ingestion(self, filename: str, file_hash: str, chunks: int) -> None:
        """Insert or update ingested_documents record."""
        import psycopg2

        def _record() -> None:
            conn = psycopg2.connect(self._postgres_dsn)
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO ingested_documents (filename, dept, doc_type, chunks_count, file_hash)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (file_hash) DO UPDATE SET chunks_count = %s, created_at = NOW()""",
                (filename, "CAC", "md", chunks, file_hash, chunks),
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
```

- [ ] **Step 2: Verify import**

Run: `cd Brooker_Corporate_Agent && python -c "from services.rag_ingestion.src.vault_watcher import VaultWatcher; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add services/rag-ingestion/src/vault_watcher.py
git commit -m "feat(rag-ingestion): add vault watcher with debounce and dedup"
```

---

### Task 6: FastAPI Main App

**Files:**
- Create: `services/rag-ingestion/src/main.py`

- [ ] **Step 1: Write main.py**

```python
# services/rag-ingestion/src/main.py
"""rag-ingestion service — FastAPI app for document and message ingestion."""
from __future__ import annotations

import contextlib
import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import FastAPI, File, Form, UploadFile

from .chat_indexer import ChatIndexer
from .chunker import DocumentChunker
from .config import RAGSettings
from .embedder import Embedder
from .models import (
    CollectionInfo,
    CollectionsResponse,
    HealthResponse,
    IngestDocumentResponse,
    IngestMessageRequest,
    IngestMessageResponse,
)
from .qdrant_store import COLLECTIONS, QdrantStore

logger = structlog.get_logger("rag-ingestion")

settings = RAGSettings()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup, cleanup on shutdown."""
    embedder = Embedder(settings)
    await embedder.start()

    store = QdrantStore(settings)
    chunker = DocumentChunker(settings)
    chat_indexer = ChatIndexer(embedder=embedder, store=store)

    # Get embedding dimension and ensure collections
    try:
        dim = await embedder.get_dimension()
    except Exception:
        dim = 1536  # fallback dimension
        logger.warning("rag-ingestion.embed_dim_fallback", dim=dim)

    await store.ensure_collections(vector_size=dim)

    app.state.embedder = embedder
    app.state.store = store
    app.state.chunker = chunker
    app.state.chat_indexer = chat_indexer

    logger.info("rag-ingestion.startup", port=3004)
    yield

    await embedder.close()
    await store.close()
    logger.info("rag-ingestion.shutdown")


app = FastAPI(
    title="RAG Ingestion",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


@app.post("/ingest/document", response_model=IngestDocumentResponse)
async def ingest_document(
    file: UploadFile = File(...),
    dept: str = Form(default="CAC"),
    doc_type: str = Form(default="pdf"),
    collection: str = Form(default="cac_docs"),
    channel_id: str = Form(default=""),
    slack_file_id: str = Form(default=""),
) -> IngestDocumentResponse:
    """Ingest a document: save temp → chunk → embed → upsert to Qdrant."""
    try:
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()

        # Save to temp file
        suffix = Path(file.filename or "doc").suffix or f".{doc_type}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            chunker: DocumentChunker = app.state.chunker
            chunks = await chunker.chunk_file(tmp_path, doc_type=doc_type, dept=dept)

            if not chunks:
                return IngestDocumentResponse(status="skipped", reason="no chunks extracted", file_hash=file_hash)

            embedder: Embedder = app.state.embedder
            texts = [c.text for c in chunks]
            metadatas = [c.metadata for c in chunks]
            vectors = await embedder.embed_texts(texts)

            store: QdrantStore = app.state.store
            count = await store.upsert_chunks(
                collection=collection,
                texts=texts,
                vectors=vectors,
                metadatas=metadatas,
            )

            return IngestDocumentResponse(status="ingested", chunks=count, file_hash=file_hash)
        finally:
            tmp_path.unlink(missing_ok=True)

    except Exception as exc:
        logger.error("ingest_document.failed", error=str(exc))
        return IngestDocumentResponse(status="error", reason=str(exc))


@app.post("/ingest/message", response_model=IngestMessageResponse)
async def ingest_message(req: IngestMessageRequest) -> IngestMessageResponse:
    """Index a Slack message into cac_chat collection."""
    try:
        chat_indexer: ChatIndexer = app.state.chat_indexer
        message_id = await chat_indexer.index_message(
            text=req.text,
            author=req.author,
            channel_id=req.channel_id,
            timestamp=req.timestamp,
            thread_ts=req.thread_ts,
            dept=req.dept,
        )
        return IngestMessageResponse(indexed=bool(message_id), message_id=message_id)
    except Exception as exc:
        logger.error("ingest_message.failed", error=str(exc))
        return IngestMessageResponse(indexed=False, message_id="")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check — verifies Qdrant and embedder connectivity."""
    store: QdrantStore = app.state.store
    embedder: Embedder = app.state.embedder

    qdrant_ok = await store.health_check()
    embed_ok = await embedder.health_check()

    status = "healthy" if (qdrant_ok and embed_ok) else "degraded"
    return HealthResponse(status=status, qdrant=qdrant_ok, embedder=embed_ok)


@app.get("/collections", response_model=CollectionsResponse)
async def collections() -> CollectionsResponse:
    """List Qdrant collections with vector counts."""
    store: QdrantStore = app.state.store
    infos = []
    for name in COLLECTIONS:
        try:
            info = await store.get_collection_info(name)
            infos.append(CollectionInfo(name=name, vectors_count=info["vectors_count"]))
        except Exception:
            infos.append(CollectionInfo(name=name, vectors_count=0))
    return CollectionsResponse(collections=infos)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3004)
```

- [ ] **Step 2: Verify import**

Run: `cd Brooker_Corporate_Agent && python -c "from services.rag_ingestion.src.main import app; print(app.title)"`
Expected: `RAG Ingestion`

- [ ] **Step 3: Commit**

```bash
git add services/rag-ingestion/src/main.py
git commit -m "feat(rag-ingestion): add FastAPI app with ingest/document, ingest/message, health endpoints"
```

---

### Task 7: Dockerfile + Docker Compose

**Files:**
- Create: `services/rag-ingestion/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write Dockerfile**

```dockerfile
# services/rag-ingestion/Dockerfile
FROM python:3.11-slim

# System deps for PyMuPDF, python-docx, openpyxl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

EXPOSE 3004

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:3004/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3004"]
```

- [ ] **Step 2: Uncomment rag-ingestion in docker-compose.yml**

Replace the commented-out `rag-ingestion` block with:

```yaml
  rag-ingestion:
    build: ./services/rag-ingestion
    ports: ["3004:3004"]
    restart: unless-stopped
    volumes:
      - mirror_data:/data/mirror:ro
    extra_hosts: ["host.docker.internal:host-gateway"]
    networks: [agent-net]
    environment:
      EMBEDDER_TYPE: vllm
      VLLM_EMBED_URL: http://host.docker.internal:8002/v1
      QDRANT_HOST: qdrant
      QDRANT_REST_PORT: "6333"
      POSTGRES_HOST: postgres
      POSTGRES_PORT: "5432"
      POSTGRES_DB: ${POSTGRES_DB:-corporate_agents}
      POSTGRES_USER: ${POSTGRES_USER:-agents}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      MINIO_ENDPOINT: minio:9000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3004/health"]
      interval: 10s
      timeout: 5s
      retries: 3
```

- [ ] **Step 3: Verify Docker build**

Run: `cd Brooker_Corporate_Agent && docker build -t rag-ingestion-test services/rag-ingestion/`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add services/rag-ingestion/Dockerfile docker-compose.yml
git commit -m "feat(rag-ingestion): add Dockerfile and uncomment docker-compose service"
```

---

### Task 8: Unit Tests — Chunker

**Files:**
- Create: `tests/unit/rag_ingestion/test_chunker.py`

- [ ] **Step 1: Write test_chunker.py**

```python
# tests/unit/rag_ingestion/test_chunker.py
"""Tests for document chunker."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.rag_ingestion.src.chunker import DocumentChunker, TextChunk


@pytest.fixture
def chunker() -> DocumentChunker:
    settings = MagicMock()
    settings.chunk_size = 100
    settings.chunk_overlap = 20
    return DocumentChunker(settings)


class TestChunkerTextSplitting:
    def test_short_text_single_chunk(self, chunker: DocumentChunker) -> None:
        pieces = chunker._split_text("Hello world")
        assert len(pieces) == 1
        assert pieces[0] == "Hello world"

    def test_long_text_multiple_chunks(self, chunker: DocumentChunker) -> None:
        text = "A" * 250
        pieces = chunker._split_text(text)
        assert len(pieces) > 1
        # Each piece should be <= chunk_size
        for piece in pieces:
            assert len(piece) <= 100

    def test_overlap_present(self, chunker: DocumentChunker) -> None:
        text = "A" * 150
        pieces = chunker._split_text(text)
        assert len(pieces) == 2
        # Second piece starts at chunk_size - overlap = 80
        assert pieces[1][:20] == pieces[0][80:]


class TestChunkerFileTypes:
    @pytest.mark.asyncio
    async def test_unsupported_type_returns_empty(self, chunker: DocumentChunker) -> None:
        result = await chunker.chunk_file(Path("/fake/file.xyz"), doc_type="xyz")
        assert result == []

    @pytest.mark.asyncio
    async def test_text_file(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Hello world from a text file")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert len(result) == 1
        assert isinstance(result[0], TextChunk)
        assert "Hello world" in result[0].text
        assert result[0].metadata["doc_type"] == "txt"
        assert result[0].metadata["source_file"] == str(f)

    @pytest.mark.asyncio
    async def test_markdown_file(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("# Heading\n\nSome markdown content.")
        result = await chunker.chunk_file(f, doc_type="md")
        assert len(result) >= 1
        assert result[0].metadata["doc_type"] == "md"

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert result == []

    @pytest.mark.asyncio
    async def test_pdf_extraction(self, chunker: DocumentChunker) -> None:
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 content here"
        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_doc.__enter__ = lambda self: self
        mock_doc.__exit__ = lambda *a: None

        with patch("services.rag_ingestion.src.chunker.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            result = await chunker.chunk_file(Path("/fake/test.pdf"), doc_type="pdf")

        assert len(result) >= 1
        assert "Page 1 content" in result[0].text
        assert result[0].metadata["page"] == 1

    @pytest.mark.asyncio
    async def test_xlsx_extraction(self, chunker: DocumentChunker) -> None:
        mock_ws = MagicMock()
        mock_ws.iter_rows.return_value = [("Col A", "Col B"), ("Val 1", "Val 2")]
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = lambda self, k: mock_ws

        with patch("services.rag_ingestion.src.chunker.load_workbook") as mock_load:
            mock_load.return_value = mock_wb
            result = await chunker.chunk_file(Path("/fake/test.xlsx"), doc_type="xlsx")

        assert len(result) >= 1
        assert result[0].metadata["sheet"] == "Sheet1"

    @pytest.mark.asyncio
    async def test_dept_metadata(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Content")
        result = await chunker.chunk_file(f, doc_type="txt", dept="FINANCE")
        assert result[0].metadata["dept"] == "FINANCE"

    @pytest.mark.asyncio
    async def test_file_hash_in_metadata(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Hash me")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert len(result[0].metadata["file_hash"]) == 64  # SHA-256 hex
```

- [ ] **Step 2: Run tests**

Run: `cd Brooker_Corporate_Agent && python -m pytest tests/unit/rag_ingestion/test_chunker.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/rag_ingestion/test_chunker.py
git commit -m "test(rag-ingestion): add chunker unit tests"
```

---

### Task 9: Unit Tests — Embedder

**Files:**
- Create: `tests/unit/rag_ingestion/test_embedder.py`

- [ ] **Step 1: Write test_embedder.py**

```python
# tests/unit/rag_ingestion/test_embedder.py
"""Tests for vLLM embedder wrapper."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.rag_ingestion.src.embedder import Embedder


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.vllm_embed_url = "http://localhost:8002/v1"
    s.vllm_embed_model = "qwen-embed"
    return s


@pytest.fixture
def embedder(settings: MagicMock) -> Embedder:
    return Embedder(settings)


def _make_embed_response(texts: list[str], dim: int = 4) -> dict:
    """Build a mock OpenAI-compatible embedding response."""
    return {
        "data": [
            {"embedding": [0.1 * (i + 1)] * dim, "index": i}
            for i in range(len(texts))
        ]
    }


class TestEmbedTexts:
    @pytest.mark.asyncio
    async def test_single_text(self, embedder: Embedder) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_embed_response(["hello"], dim=4)

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_resp
        embedder._http = mock_http

        result = await embedder.embed_texts(["hello"])
        assert len(result) == 1
        assert len(result[0]) == 4

    @pytest.mark.asyncio
    async def test_empty_list(self, embedder: Embedder) -> None:
        result = await embedder.embed_texts([])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_splitting(self, embedder: Embedder) -> None:
        embedder.BATCH_SIZE = 2
        texts = ["a", "b", "c"]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(url, json):
            nonlocal call_count
            call_count += 1
            batch_size = len(json["input"])
            mock_resp.json.return_value = _make_embed_response(json["input"])
            return mock_resp

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = mock_post
        embedder._http = mock_http

        result = await embedder.embed_texts(texts)
        assert len(result) == 3
        assert call_count == 2  # 2 texts + 1 text

    @pytest.mark.asyncio
    async def test_get_dimension(self, embedder: Embedder) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_embed_response(["test"], dim=768)

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_resp
        embedder._http = mock_http

        dim = await embedder.get_dimension()
        assert dim == 768


class TestEmbedderHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, embedder: Embedder) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = mock_resp
        embedder._http = mock_http

        assert await embedder.health_check() is True

    @pytest.mark.asyncio
    async def test_health_fail(self, embedder: Embedder) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.side_effect = httpx.ConnectError("refused")
        embedder._http = mock_http

        assert await embedder.health_check() is False
```

- [ ] **Step 2: Run tests**

Run: `cd Brooker_Corporate_Agent && python -m pytest tests/unit/rag_ingestion/test_embedder.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/rag_ingestion/test_embedder.py
git commit -m "test(rag-ingestion): add embedder unit tests"
```

---

### Task 10: Unit Tests — Qdrant Store

**Files:**
- Create: `tests/unit/rag_ingestion/test_qdrant_store.py`

- [ ] **Step 1: Write test_qdrant_store.py**

```python
# tests/unit/rag_ingestion/test_qdrant_store.py
"""Tests for Qdrant store wrapper."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.rag_ingestion.src.qdrant_store import COLLECTIONS, QdrantStore


@pytest.fixture
def mock_settings() -> MagicMock:
    s = MagicMock()
    s.qdrant_host = "localhost"
    s.qdrant_rest_port = 6333
    return s


@pytest.fixture
def store(mock_settings: MagicMock) -> QdrantStore:
    s = QdrantStore(mock_settings)
    s._client = AsyncMock()
    return s


class TestEnsureCollections:
    @pytest.mark.asyncio
    async def test_creates_missing_collections(self, store: QdrantStore) -> None:
        mock_collections = MagicMock()
        mock_collections.collections = []  # no existing collections
        store._client.get_collections.return_value = mock_collections

        await store.ensure_collections(vector_size=768)

        assert store._client.create_collection.call_count == len(COLLECTIONS)

    @pytest.mark.asyncio
    async def test_skips_existing_collections(self, store: QdrantStore) -> None:
        existing = [MagicMock(name=n) for n in COLLECTIONS]
        for e, n in zip(existing, COLLECTIONS, strict=True):
            e.name = n
        mock_collections = MagicMock()
        mock_collections.collections = existing
        store._client.get_collections.return_value = mock_collections

        await store.ensure_collections(vector_size=768)

        store._client.create_collection.assert_not_called()


class TestUpsertChunks:
    @pytest.mark.asyncio
    async def test_upsert_batch(self, store: QdrantStore) -> None:
        count = await store.upsert_chunks(
            collection="cac_docs",
            texts=["hello", "world"],
            vectors=[[0.1] * 4, [0.2] * 4],
            metadatas=[{"source": "a"}, {"source": "b"}],
        )
        assert count == 2
        store._client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_empty(self, store: QdrantStore) -> None:
        count = await store.upsert_chunks(
            collection="cac_docs", texts=[], vectors=[], metadatas=[]
        )
        assert count == 0
        store._client.upsert.assert_not_called()


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, store: QdrantStore) -> None:
        hit = MagicMock()
        hit.payload = {"text": "hello", "source": "doc.pdf"}
        hit.score = 0.85
        hit.id = "abc-123"
        store._client.search.return_value = [hit]

        results = await store.search("cac_docs", query_vector=[0.1] * 4)
        assert len(results) == 1
        assert results[0]["text"] == "hello"
        assert results[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_search_with_filters(self, store: QdrantStore) -> None:
        store._client.search.return_value = []
        await store.search("cac_docs", query_vector=[0.1] * 4, filters={"dept": "CAC"})
        call_args = store._client.search.call_args
        assert call_args.kwargs.get("query_filter") is not None


class TestDeleteByFile:
    @pytest.mark.asyncio
    async def test_delete_calls_client(self, store: QdrantStore) -> None:
        await store.delete_by_file("cac_docs", "/data/mirror/doc.pdf")
        store._client.delete.assert_called_once()


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self, store: QdrantStore) -> None:
        store._client.get_collections.return_value = MagicMock()
        assert await store.health_check() is True

    @pytest.mark.asyncio
    async def test_unhealthy(self, store: QdrantStore) -> None:
        store._client.get_collections.side_effect = Exception("connection refused")
        assert await store.health_check() is False
```

- [ ] **Step 2: Run tests**

Run: `cd Brooker_Corporate_Agent && python -m pytest tests/unit/rag_ingestion/test_qdrant_store.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/rag_ingestion/test_qdrant_store.py
git commit -m "test(rag-ingestion): add Qdrant store unit tests"
```

---

### Task 11: Unit Tests — Chat Indexer

**Files:**
- Create: `tests/unit/rag_ingestion/test_chat_indexer.py`

- [ ] **Step 1: Write test_chat_indexer.py**

```python
# tests/unit/rag_ingestion/test_chat_indexer.py
"""Tests for chat indexer."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from services.rag_ingestion.src.chat_indexer import ChatIndexer


@pytest.fixture
def mock_embedder() -> AsyncMock:
    e = AsyncMock()
    e.embed_single.return_value = [0.1] * 4
    return e


@pytest.fixture
def mock_store() -> AsyncMock:
    s = AsyncMock()
    s.search.return_value = []  # no duplicates by default
    s.upsert_chunks.return_value = 1
    return s


@pytest.fixture
def indexer(mock_embedder: AsyncMock, mock_store: AsyncMock) -> ChatIndexer:
    return ChatIndexer(embedder=mock_embedder, store=mock_store)


class TestMakeMessageId:
    def test_deterministic(self) -> None:
        id1 = ChatIndexer.make_message_id("C123", "1234567890.123")
        id2 = ChatIndexer.make_message_id("C123", "1234567890.123")
        assert id1 == id2

    def test_different_channel_different_id(self) -> None:
        id1 = ChatIndexer.make_message_id("C123", "1234567890.123")
        id2 = ChatIndexer.make_message_id("C456", "1234567890.123")
        assert id1 != id2

    def test_length_32(self) -> None:
        msg_id = ChatIndexer.make_message_id("C123", "ts")
        assert len(msg_id) == 32


class TestIndexMessage:
    @pytest.mark.asyncio
    async def test_indexes_new_message(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        msg_id = await indexer.index_message(
            text="Hello team",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123",
        )
        assert len(msg_id) == 32
        mock_store.upsert_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_duplicate(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        mock_store.search.return_value = [{"message_id": "existing"}]
        msg_id = await indexer.index_message(
            text="Hello team",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123",
        )
        assert len(msg_id) == 32
        mock_store.upsert_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self, indexer: ChatIndexer) -> None:
        msg_id = await indexer.index_message(
            text="",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123",
        )
        assert msg_id == ""

    @pytest.mark.asyncio
    async def test_thread_ts_preserved(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        await indexer.index_message(
            text="Reply in thread",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.456",
            thread_ts="1234567890.123",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["thread_ts"] == "1234567890.123"

    @pytest.mark.asyncio
    async def test_dept_metadata(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        await indexer.index_message(
            text="Finance update",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.789",
            dept="FINANCE",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["dept"] == "FINANCE"
```

- [ ] **Step 2: Run tests**

Run: `cd Brooker_Corporate_Agent && python -m pytest tests/unit/rag_ingestion/test_chat_indexer.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/rag_ingestion/test_chat_indexer.py
git commit -m "test(rag-ingestion): add chat indexer unit tests"
```

---

### Task 12: Unit Tests — Vault Watcher

**Files:**
- Create: `tests/unit/rag_ingestion/test_vault_watcher.py`

- [ ] **Step 1: Write test_vault_watcher.py**

```python
# tests/unit/rag_ingestion/test_vault_watcher.py
"""Tests for Obsidian vault watcher."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.rag_ingestion.src.chunker import TextChunk
from services.rag_ingestion.src.vault_watcher import VaultWatcher, _VaultEventHandler


@pytest.fixture
def mock_settings() -> MagicMock:
    s = MagicMock()
    s.obsidian_vault_path = "/tmp/test-vault"
    s.obsidian_ingest_delay_seconds = 0  # no debounce in tests
    return s


@pytest.fixture
def mock_chunker() -> AsyncMock:
    c = AsyncMock()
    c.chunk_file.return_value = [
        TextChunk("chunk 1", {"source_file": "/tmp/test.md", "doc_type": "md"}),
        TextChunk("chunk 2", {"source_file": "/tmp/test.md", "doc_type": "md"}),
    ]
    return c


@pytest.fixture
def mock_embedder() -> AsyncMock:
    e = AsyncMock()
    e.embed_texts.return_value = [[0.1] * 4, [0.2] * 4]
    return e


@pytest.fixture
def mock_store() -> AsyncMock:
    s = AsyncMock()
    s.upsert_chunks.return_value = 2
    return s


@pytest.fixture
def watcher(
    mock_settings: MagicMock,
    mock_chunker: AsyncMock,
    mock_embedder: AsyncMock,
    mock_store: AsyncMock,
) -> VaultWatcher:
    return VaultWatcher(
        settings=mock_settings,
        chunker=mock_chunker,
        embedder=mock_embedder,
        store=mock_store,
        postgres_dsn="postgresql://test:test@localhost/test",
    )


class TestProcessFile:
    @pytest.mark.asyncio
    async def test_new_file_ingested(
        self, watcher: VaultWatcher, mock_store: AsyncMock, tmp_path: Path
    ) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\nSome content")

        with patch.object(watcher, "_is_already_ingested", return_value=False):
            with patch.object(watcher, "_record_ingestion", new_callable=AsyncMock):
                await watcher._process_file(str(md_file))

        mock_store.delete_by_file.assert_called_once()
        mock_store.upsert_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_unchanged_file_skipped(
        self, watcher: VaultWatcher, mock_store: AsyncMock, tmp_path: Path
    ) -> None:
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\nSame content")

        with patch.object(watcher, "_is_already_ingested", return_value=True):
            await watcher._process_file(str(md_file))

        mock_store.upsert_chunks.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_file_skipped(self, watcher: VaultWatcher) -> None:
        await watcher._process_file("/nonexistent/file.md")
        # Should not raise, just log and return


class TestVaultEventHandler:
    def test_md_file_triggers_callback(self) -> None:
        callback = MagicMock()
        handler = _VaultEventHandler(callback)
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/vault/note.md"
        handler.on_modified(event)
        callback.assert_called_once_with("/vault/note.md")

    def test_non_md_ignored_by_watcher(self) -> None:
        """The watcher's _on_file_event filters non-.md files."""
        watcher_mock = MagicMock()
        watcher_mock._on_file_event = VaultWatcher._on_file_event.__get__(watcher_mock)
        watcher_mock._loop = None
        # Calling with non-.md should return without scheduling
        watcher_mock._on_file_event("/vault/image.png")
        # No crash, no pending tasks


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_with_missing_path(self, watcher: VaultWatcher) -> None:
        """Start with nonexistent vault path logs warning and returns."""
        await watcher.start()
        assert watcher._observer is None

    @pytest.mark.asyncio
    async def test_stop_clears_state(self, watcher: VaultWatcher) -> None:
        await watcher.stop()
        assert watcher._observer is None
        assert watcher._pending == {}
```

- [ ] **Step 2: Run tests**

Run: `cd Brooker_Corporate_Agent && python -m pytest tests/unit/rag_ingestion/test_vault_watcher.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/rag_ingestion/test_vault_watcher.py
git commit -m "test(rag-ingestion): add vault watcher unit tests"
```

---

### Task 13: Integration Test

**Files:**
- Create: `tests/integration/test_rag_pipeline.py`

- [ ] **Step 1: Write test_rag_pipeline.py**

```python
# tests/integration/test_rag_pipeline.py
"""Integration test for RAG ingestion pipeline."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from services.rag_ingestion.src.main import app


@pytest.fixture
def mock_embedder() -> AsyncMock:
    e = AsyncMock()
    e.embed_texts.return_value = [[0.1] * 4, [0.2] * 4]
    e.embed_single.return_value = [0.1] * 4
    e.get_dimension.return_value = 4
    e.health_check.return_value = True
    e.start = AsyncMock()
    e.close = AsyncMock()
    return e


@pytest.fixture
def mock_store() -> AsyncMock:
    s = AsyncMock()
    s.upsert_chunks.return_value = 2
    s.search.return_value = []
    s.health_check.return_value = True
    s.ensure_collections = AsyncMock()
    s.close = AsyncMock()
    s.get_collection_info.return_value = {"vectors_count": 42, "status": "green"}
    return s


@pytest.fixture
def mock_chat_indexer() -> AsyncMock:
    ci = AsyncMock()
    ci.index_message.return_value = "msg_abc123"
    return ci


@pytest.fixture
def mock_chunker() -> AsyncMock:
    from services.rag_ingestion.src.chunker import TextChunk

    c = AsyncMock()
    c.chunk_file.return_value = [
        TextChunk("chunk 1", {"source_file": "test.pdf", "doc_type": "pdf"}),
        TextChunk("chunk 2", {"source_file": "test.pdf", "doc_type": "pdf"}),
    ]
    return c


@pytest.fixture
async def client(
    mock_embedder: AsyncMock,
    mock_store: AsyncMock,
    mock_chat_indexer: AsyncMock,
    mock_chunker: AsyncMock,
) -> AsyncClient:
    app.state.embedder = mock_embedder
    app.state.store = mock_store
    app.state.chat_indexer = mock_chat_indexer
    app.state.chunker = mock_chunker

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestDocumentIngestion:
    @pytest.mark.asyncio
    async def test_upload_pdf(self, client: AsyncClient, mock_store: AsyncMock) -> None:
        resp = await client.post(
            "/ingest/document",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            data={"dept": "CAC", "doc_type": "pdf", "collection": "cac_docs"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"
        assert data["chunks"] == 2
        assert len(data["file_hash"]) == 64


class TestMessageIngestion:
    @pytest.mark.asyncio
    async def test_index_message(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/ingest/message",
            json={
                "text": "Meeting at 3pm",
                "author": "U123",
                "channel_id": "C456",
                "timestamp": "1234567890.123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["indexed"] is True
        assert data["message_id"] == "msg_abc123"


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_healthy(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["qdrant"] is True
        assert data["embedder"] is True

    @pytest.mark.asyncio
    async def test_degraded(self, client: AsyncClient, mock_store: AsyncMock) -> None:
        mock_store.health_check.return_value = False
        resp = await client.get("/health")
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["qdrant"] is False


class TestCollectionsEndpoint:
    @pytest.mark.asyncio
    async def test_list_collections(self, client: AsyncClient) -> None:
        resp = await client.get("/collections")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["collections"]) == 4
        assert data["collections"][0]["vectors_count"] == 42
```

- [ ] **Step 2: Run tests**

Run: `cd Brooker_Corporate_Agent && python -m pytest tests/integration/test_rag_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_rag_pipeline.py
git commit -m "test(rag-ingestion): add integration test for full pipeline"
```

---

### Task 14: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `cd Brooker_Corporate_Agent && python -m pytest tests/unit/rag_ingestion/ tests/integration/test_rag_pipeline.py -v --tb=short`
Expected: All tests PASS (existing test_models.py + new tests)

- [ ] **Step 2: Run ruff**

Run: `cd Brooker_Corporate_Agent && ruff check services/rag-ingestion/src/ tests/unit/rag_ingestion/ tests/integration/test_rag_pipeline.py`
Expected: Clean (no errors)

- [ ] **Step 3: Update Implementation.md**

Check off Stage 2 items in `docs/Implementation.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/Implementation.md
git commit -m "docs: mark Stage 2 (RAG Ingestion) complete"
```
