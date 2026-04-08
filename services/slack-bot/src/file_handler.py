"""Download Slack files and forward to rag-ingestion."""
from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import structlog

from .models import SlackFileInfo

logger = structlog.get_logger("slack-bot.file_handler")

SUPPORTED_TYPES: frozenset[str] = frozenset({"pdf", "xlsx", "docx", "txt", "md"})


MAX_FILE_SIZE_MB = 50  # Default; overridable via config


async def download_and_forward_file(
    *,
    file_info: SlackFileInfo,
    channel_id: str,
    bot_token: str,
    rag_client,
    http: httpx.AsyncClient | None = None,
    allowed_types: frozenset[str] = SUPPORTED_TYPES,
    max_file_size_mb: int = MAX_FILE_SIZE_MB,
) -> dict:
    """Download file from Slack, POST to rag-ingestion, clean up.

    Returns response dict from rag-ingestion or {"status": "skipped"}.
    """
    filetype = file_info.filetype.lower()
    if filetype not in allowed_types:
        logger.warning(
            "file_handler.unsupported_type",
            filetype=filetype,
            file_id=file_info.id,
        )
        return {"status": "skipped", "reason": f"unsupported type: {filetype}"}

    max_bytes = max_file_size_mb * 1024 * 1024
    if file_info.size > max_bytes:
        logger.warning(
            "file_handler.file_too_large",
            file_id=file_info.id,
            size=file_info.size,
            max_bytes=max_bytes,
        )
        return {"status": "skipped", "reason": f"file too large: {file_info.size} bytes"}

    tmp_path = await _download_to_temp(file_info, bot_token, http)
    try:
        file_bytes = tmp_path.read_bytes()
        result = await rag_client.upload_file(
            file_bytes=file_bytes,
            filename=file_info.name,
            filetype=filetype,
            channel_id=channel_id,
            file_id=file_info.id,
        )
        logger.info(
            "file_handler.forwarded",
            file_id=file_info.id,
            status=result.get("status"),
            chunks=result.get("chunks", 0),
        )
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


async def _download_to_temp(
    file_info: SlackFileInfo,
    bot_token: str,
    http: httpx.AsyncClient | None,
) -> Path:
    """Stream Slack private download URL to a temp file.

    Caller is responsible for deletion.
    """
    owns_client = http is None
    if owns_client:
        http = httpx.AsyncClient()

    try:
        response = await http.get(
            file_info.url_private_download,
            headers={"Authorization": f"Bearer {bot_token}"},
            follow_redirects=True,
        )
        response.raise_for_status()

        suffix = f".{file_info.filetype}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)

        logger.debug("file_handler.downloaded", file_id=file_info.id, bytes=len(response.content))
        return tmp_path
    finally:
        if owns_client:
            await http.aclose()
