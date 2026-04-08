# services/rag-ingestion/src/main.py
"""rag-ingestion service — FastAPI app for document and message ingestion."""
from __future__ import annotations

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
WIKI_COMPILER_URL = os.getenv("WIKI_COMPILER_URL", "http://wiki-compiler:3007")


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
    file: UploadFile = File(...),  # noqa: B008
    dept: str = Form(default="CAC"),
    doc_type: str = Form(default="pdf"),
    collection: str = Form(default="cac_docs"),
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
            chunks = await chunker.chunk_file(tmp_path, doc_type=doc_type, dept=dept)

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
