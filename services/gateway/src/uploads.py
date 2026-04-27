"""Upload proxy — forwards file uploads to rag-ingestion service."""
from __future__ import annotations

import os

import httpx
import structlog
from fastapi import APIRouter, File, Form, UploadFile

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

RAG_INGESTION_URL = os.getenv("RAG_INGESTION_URL", "http://localhost:3004")


@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    dept: str = Form(default="cac"),
    doc_type: str = Form(default="pdf"),
    collection: str = Form(default="cac_docs"),
    category: str = Form(default=""),
    tags: str = Form(default=""),
    description: str = Form(default=""),
    source: str = Form(default="manual_upload"),
) -> dict:
    """Proxy file upload to rag-ingestion /ingest/document."""
    content = await file.read()

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{RAG_INGESTION_URL}/ingest/document",
            files={"file": (file.filename, content, file.content_type or "application/octet-stream")},
            data={
                "dept": dept,
                "doc_type": doc_type,
                "collection": collection,
                "category": category,
                "tags": tags,
                "description": description,
                "source": source,
            },
        )

    if resp.status_code != 200:
        logger.error("upload_proxy.failed", status=resp.status_code, body=resp.text[:200])
        return {"status": "error", "reason": f"rag-ingestion returned {resp.status_code}"}

    result = resp.json()
    logger.info(
        "upload_proxy.success",
        filename=file.filename,
        collection=collection,
        category=category,
        status=result.get("status"),
        chunks=result.get("chunks", 0),
    )
    return result
