"""Format and post Slack replies."""
from __future__ import annotations

import structlog

from .models import Citation, QueryResponse

logger = structlog.get_logger("slack-bot.responder")


def format_response(response: QueryResponse) -> tuple[str, list[dict] | None]:
    """Build Block Kit blocks from a QueryResponse.

    Returns (fallback_text, blocks_list).
    """
    if response.error:
        return f"Error: {response.error}", None

    fallback = response.answer

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": response.answer},
        }
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

    if response.confidence > 0:
        confidence_pct = int(response.confidence * 100)
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"_Confidence: {confidence_pct}%_"},
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


async def reply_in_thread(
    client: object,
    channel: str,
    thread_ts: str,
    content: str | QueryResponse,
) -> None:
    """Post a message into the thread identified by (channel, thread_ts)."""
    if isinstance(content, str):
        text = content
        blocks = None
    else:
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
