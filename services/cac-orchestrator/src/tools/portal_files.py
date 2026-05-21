"""Fetch portal-uploaded files and extract them via rag-ingestion's /extract.

Used pre-graph to inject the contents of files attached to a chat turn into
the LLM context. Authenticated with the caller's JWT (passed through from
the gateway) so the portal enforces per-file access control.
"""
from __future__ import annotations

import os

import httpx
import structlog

from ..models import AttachedFile

logger = structlog.get_logger("portal_files")

_RAG_INGESTION_URL = os.getenv("RAG_INGESTION_URL", "http://rag-ingestion:3004")


async def fetch_and_extract(
    files: list[AttachedFile],
    portal_base_url: str | None,
    auth_token: str | None,
    max_chars_per_file: int = 20_000,
    timeout_s: float = 30.0,
) -> str:
    """Pull every file from the portal, extract text via rag-ingestion, return joined context.

    Returns an empty string if there are no files or if the portal/extract path
    isn't usable — file fetching is best-effort and must never crash a query.
    """
    if not files or not portal_base_url or not auth_token:
        return ""

    portal_base_url = portal_base_url.rstrip("/")
    pieces: list[str] = []

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for f in files:
            try:
                file_resp = await client.get(
                    f"{portal_base_url}/api/paperclip/files/{f.id}",
                    headers={"Authorization": f"Bearer {auth_token}"},
                )
                if file_resp.status_code != 200:
                    logger.warning(
                        "portal_file_fetch_failed",
                        file_id=f.id,
                        status=file_resp.status_code,
                    )
                    continue

                extract_resp = await client.post(
                    f"{_RAG_INGESTION_URL}/extract",
                    files={
                        "file": (
                            f.name or f.id,
                            file_resp.content,
                            f.mimetype or "application/octet-stream",
                        ),
                    },
                )
                if extract_resp.status_code != 200:
                    logger.warning(
                        "portal_file_extract_failed",
                        file_id=f.id,
                        status=extract_resp.status_code,
                    )
                    continue

                data = extract_resp.json()
                text = "\n\n".join(c.get("text", "") for c in data.get("chunks", []))
                if not text.strip():
                    continue

                trimmed = text[:max_chars_per_file]
                pieces.append(
                    f"--- Attached file: {f.name or f.id} ---\n{trimmed}"
                )
            except Exception as exc:
                logger.warning(
                    "portal_file_processing_error",
                    file_id=f.id,
                    error=str(exc),
                )

    if not pieces:
        return ""
    return "\n\n".join(pieces)
