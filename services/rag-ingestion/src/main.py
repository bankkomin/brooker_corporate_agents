# services/rag-ingestion/src/main.py
"""rag-ingestion service — FastAPI app for document and message ingestion."""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import contextlib
import hashlib
import os
import tempfile
from pathlib import Path

import httpx
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
WIKI_COMPILER_URL = os.getenv("WIKI_COMPILER_URL", "http://localhost:3007")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup, cleanup on shutdown."""
    embedder = Embedder(settings)
    await embedder.start()

    store = QdrantStore(settings)
    chunker = DocumentChunker(settings)
    chat_indexer = ChatIndexer(embedder=embedder, store=store)

    # Get embedding dimension and ensure collections.
    # Priority: EMBEDDING_DIM env var > auto-detect from vLLM > fail fast.
    # Qwen3.5 9B produces 4096-dimensional vectors; 1536 would silently corrupt
    # all Qdrant collections created at startup, so we never fall back silently.
    _env_dim = os.getenv("EMBEDDING_DIM")
    if _env_dim:
        try:
            dim = int(_env_dim)
        except ValueError as exc:
            logger.error(
                "rag-ingestion.startup.invalid_embedding_dim",
                embedding_dim_env=_env_dim,
                error=str(exc),
            )
            raise RuntimeError(
                f"EMBEDDING_DIM env var is not a valid integer: {_env_dim!r}"
            ) from exc
        logger.info("rag-ingestion.startup.embedding_dim_from_env", dim=dim)
    else:
        try:
            dim = await embedder.get_dimension()
            logger.info("rag-ingestion.startup.embedding_dim_detected", dim=dim)
        except Exception as exc:
            logger.error(
                "rag-ingestion.startup.embedding_dim_detection_failed",
                embedder_type=settings.embedder_type,
                error=str(exc),
            )
            raise RuntimeError(
                f"Cannot determine embedding dimension: {settings.embedder_type} embedder "
                f"is unreachable. Set EMBEDDING_DIM env var to override."
            ) from exc

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
    file: UploadFile = File(...),  # noqa: B008
    dept: str = Form(default="CAC"),
    doc_type: str = Form(default="pdf"),
    collection: str = Form(default="cac_docs"),
    category: str = Form(default=""),
    tags: str = Form(default=""),
    description: str = Form(default=""),
    source: str = Form(default="manual_upload"),
    channel_id: str = Form(default=""),
    slack_file_id: str = Form(default=""),
) -> IngestDocumentResponse:
    """Ingest a document: save temp -> chunk -> embed -> upsert to Qdrant."""
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
            extra_meta = {
                "category": category,
                "tags": tags,
                "description": description,
                "source": source,
                "original_filename": file.filename or "",
            }
            chunks = await chunker.chunk_file(
                tmp_path, doc_type=doc_type, dept=dept, extra_meta=extra_meta,
            )

            if not chunks:
                return IngestDocumentResponse(
                    status="skipped",
                    reason="no chunks extracted",
                    file_hash=file_hash,
                )

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

            # Notify wiki-compiler (fire-and-forget)
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{WIKI_COMPILER_URL}/compile",
                        json={
                            "event_type": "document_ingested",
                            "dept_id": dept,
                            "payload": {
                                "filename": file.filename,
                                "doc_type": doc_type,
                                "dept": dept,
                                "chunks_count": count,
                                "file_hash": file_hash,
                            },
                        },
                        timeout=5.0,
                    )
            except Exception:
                logger.warning("wiki_compile_notify_failed", filename=file.filename)

            return IngestDocumentResponse(
                status="ingested", chunks=count, file_hash=file_hash
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    except Exception as exc:
        logger.error("ingest_document.failed", error=str(exc))
        return IngestDocumentResponse(status="error", reason=str(exc))


@app.post("/extract")
async def extract_document(
    file: UploadFile = File(...),  # noqa: B008
    doc_type: str = Form(default=""),
) -> dict:
    """Chunk a file into text segments WITHOUT embedding or storing.

    Used for transient context injection — e.g., portal-uploaded files
    attached to a single chat turn that shouldn't be persisted.
    """
    content = await file.read()
    suffix = Path(file.filename or "doc").suffix.lstrip(".")
    inferred_type = doc_type or suffix or "pdf"

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=f".{inferred_type}",
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        chunker: DocumentChunker = app.state.chunker
        chunks = await chunker.chunk_file(
            tmp_path, doc_type=inferred_type, dept="transient",
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "filename": file.filename,
        "doc_type": inferred_type,
        "chunks": [
            {"text": c.text, "metadata": c.metadata} for c in chunks
        ],
    }


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


@app.post("/embed")
async def embed(req: dict) -> dict:
    """Embed a single string or a list of strings; returns vectors.

    Body: {"text": "..."} or {"texts": ["...", "..."]}.
    """
    embedder: Embedder = app.state.embedder
    if "text" in req:
        vec = await embedder.embed_single(req["text"])
        return {"vector": vec, "dim": len(vec)}
    vecs = await embedder.embed_texts(req.get("texts", []))
    return {"vectors": vecs, "dim": len(vecs[0]) if vecs else 0}


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
