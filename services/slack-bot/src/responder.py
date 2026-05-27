"""Format and post Slack replies."""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import structlog

from .models import Citation, QueryResponse

logger = structlog.get_logger("slack-bot.responder")

_FILE_FETCH_TIMEOUT = 30.0


# Slack section text has a hard 3000-char limit; stay safely under it.
_SECTION_LIMIT = 2900
# Slack allows max 50 blocks per message; reserve a few for citations/confidence.
_MAX_TEXT_BLOCKS = 45


def _split_for_blocks(text: str, limit: int = _SECTION_LIMIT) -> list[str]:
    """Split text into <=limit chunks on line boundaries (markdown-friendly)."""
    chunks: list[str] = []
    cur = ""
    for line in text.split("\n"):
        while len(line) > limit:  # a single over-long line: hard-split it
            chunks.append(line[:limit])
            line = line[limit:]
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks


def format_response(response: QueryResponse) -> tuple[str, list[dict] | None]:
    """Build Block Kit blocks from a QueryResponse.

    Returns (fallback_text, blocks_list).
    """
    if response.error:
        return f"Error: {response.error}", None

    fallback = response.answer

    # Long answers (e.g. a full CAC report) exceed Slack's 3000-char/section
    # limit, so split across multiple section blocks.
    parts = _split_for_blocks(response.answer)
    if len(parts) > _MAX_TEXT_BLOCKS:
        parts = parts[:_MAX_TEXT_BLOCKS]
        parts[-1] += "\n\n_…truncated. Full report available via the data pack._"
    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": part}}
        for part in parts
    ]

    if response.citations:
        citation_lines = _format_citations(response.citations)
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Sources*\n{citation_lines}"},
                ],
            }
        )

    if response.confidence:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"_Confidence: {response.confidence}_"},
                ],
            }
        )

    return fallback, blocks


def _format_citations(citations: list[Citation]) -> str:
    """Render citations as a compact numbered list."""
    lines = []
    for i, c in enumerate(citations, start=1):
        excerpt = c.excerpt[:120] + "..." if len(c.excerpt) > 120 else c.excerpt
        lines.append(f"{i}. *{c.source}* - _{excerpt}_")
    return "\n".join(lines)


async def _upload_artefact(client: object, channel: str, thread_ts: str, response: QueryResponse) -> None:
    """If the response carries a file (deck-writer etc.), upload it to the thread."""
    name = response.file_name or (Path(response.file_path).name if response.file_path else None)
    if not name:
        return
    payload_bytes: bytes | None = None
    # Prefer HTTP fetch via the producing service (works across containers without shared mounts).
    if response.file_url:
        try:
            async with httpx.AsyncClient(timeout=_FILE_FETCH_TIMEOUT) as h:
                r = await h.get(response.file_url)
                r.raise_for_status()
                payload_bytes = r.content
        except Exception as exc:
            logger.warning("responder.file_fetch_failed", url=response.file_url, error=str(exc))
    # Fallback to local path if mounted in this container.
    if payload_bytes is None and response.file_path and os.path.isfile(response.file_path):
        payload_bytes = Path(response.file_path).read_bytes()
    if payload_bytes is None:
        logger.warning("responder.file_unavailable", file=name)
        return
    try:
        await client.files_upload_v2(  # type: ignore[attr-defined]
            channel=channel,
            thread_ts=thread_ts,
            filename=name,
            content=payload_bytes,
            initial_comment=f":page_facing_up: {name}",
        )
        logger.info("responder.file_uploaded", file=name, channel=channel, bytes=len(payload_bytes))
    except Exception as exc:
        logger.error("responder.file_upload_failed", file=name, error=str(exc))


async def reply_in_thread(
    client: object,
    channel: str,
    thread_ts: str,
    content: str | QueryResponse,
) -> None:
    """Post a message into the thread identified by (channel, thread_ts).

    If `content` is a QueryResponse carrying a file_url/file_path, also upload
    that file into the thread before the text reply.
    """
    if isinstance(content, str):
        text = content
        blocks = None
    else:
        if content.file_url or content.file_path:
            await _upload_artefact(client, channel, thread_ts, content)
        text, blocks = format_response(content)

    try:
        await client.chat_postMessage(  # type: ignore[attr-defined]
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks,
        )
        logger.info("responder.replied", channel=channel, thread_ts=thread_ts)
    except Exception as exc:
        logger.error("responder.post_failed", channel=channel, error=str(exc))


async def post_error_to_thread(
    client: object,
    channel: str,
    thread_ts: str,
    exc: Exception,
) -> None:
    """Send a user-facing error message to the thread."""
    msg = (
        "Sorry, I ran into an error processing your request. "
        "The team has been notified. Please try again shortly."
    )
    logger.error("responder.error_reply", channel=channel, error=str(exc))
    await reply_in_thread(client, channel, thread_ts, msg)
