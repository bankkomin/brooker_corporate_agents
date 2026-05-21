"""Bolt event handler registrations."""
from __future__ import annotations

import asyncio
import re

import structlog
from slack_bolt.async_app import AsyncApp

from .clients import OrchestratorClient, RAGIngestionClient
from .file_handler import download_and_forward_file
from .models import SlackFileInfo
from .responder import post_error_to_thread, reply_in_thread

logger = structlog.get_logger("slack-bot.events")

# Known department ids (match the orchestrator's _DEPT_ROUTES). Used to map a
# Slack channel name like "#risk-committee" → dept "risk" so each committee
# channel behaves as its own department without needing a [dept] prefix.
_DEPTS = {
    "cac", "risk", "legal", "hr", "it", "ceo",
    "finance", "ib", "ic", "cio", "vcc", "comms",
}
# channel_id -> dept_id (or None). Cached so we don't hit conversations.info per message.
_channel_dept_cache: dict[str, str | None] = {}


def _dept_from_channel_name(name: str) -> str | None:
    """Map a channel name to a dept id by token match. e.g. 'risk-committee'
    -> 'risk', 'hr-head' -> 'hr'. Returns None for general channels like
    'all-brook-corporate-ai-agents' (no dept token)."""
    tokens = name.lower().replace("_", "-").split("-")
    for d in _DEPTS:
        if d in tokens:
            return d
    return None


async def _resolve_channel_dept(client, channel_id: str) -> str | None:
    """Resolve a channel_id to a dept id via its name (cached)."""
    if channel_id in _channel_dept_cache:
        return _channel_dept_cache[channel_id]
    dept: str | None = None
    try:
        info = await client.conversations_info(channel=channel_id)
        name = info["channel"]["name"]
        dept = _dept_from_channel_name(name)
        logger.info("events.channel_dept_resolved", channel=channel_id, name=name, dept=dept)
    except Exception as exc:
        # Missing channels:read scope or a DM — fall back to default routing.
        logger.warning("events.channel_dept_unresolved", channel=channel_id, error=str(exc))
    _channel_dept_cache[channel_id] = dept
    return dept


def register_event_handlers(
    bolt_app: AsyncApp,
    rag_client: RAGIngestionClient,
    orch_client: OrchestratorClient,
    bot_token: str,
) -> None:
    """Attach all Bolt listeners. Each handler ACKs then creates a background task."""

    @bolt_app.event("message")
    async def handle_message(event: dict, ack, **kwargs) -> None:
        await ack()
        if event.get("subtype") == "bot_message" or event.get("bot_id"):
            return
        asyncio.create_task(
            _safe_process(_process_message(event, rag_client)),
            name="ingest_message",
        )

    @bolt_app.event("file_shared")
    async def handle_file_shared(event: dict, client, ack, **kwargs) -> None:
        await ack()
        asyncio.create_task(
            _safe_process(
                _process_file(event, client, rag_client, bot_token)
            ),
            name="ingest_file",
        )

    @bolt_app.event("app_mention")
    async def handle_app_mention(event: dict, client, ack, **kwargs) -> None:
        await ack()
        asyncio.create_task(
            _safe_process(
                _process_mention(event, client, rag_client, orch_client)
            ),
            name="query_orchestrator",
        )


async def _safe_process(coro) -> None:
    """Wrap a coroutine to catch and log all exceptions."""
    try:
        await coro
    except Exception as exc:
        logger.error("events.background_task_failed", error=str(exc), exc_info=True)


async def _process_message(event: dict, rag_client: RAGIngestionClient) -> None:
    """Send message text to rag-ingestion for indexing."""
    await rag_client.index_message(
        text=event.get("text", ""),
        author=event.get("user", "unknown"),
        channel_id=event.get("channel", ""),
        timestamp=event.get("ts", ""),
        thread_ts=event.get("thread_ts"),
    )


async def _process_file(
    event: dict,
    client,
    rag_client: RAGIngestionClient,
    bot_token: str,
) -> None:
    """Retrieve file metadata from Slack, download, and forward to rag-ingestion."""
    file_id: str = event.get("file_id", "")
    channel_id: str = event.get("channel_id", "")
    try:
        info = await client.files_info(file=file_id)
        file_obj = info["file"]
        file_info = SlackFileInfo(
            id=file_obj["id"],
            name=file_obj["name"],
            mimetype=file_obj["mimetype"],
            url_private_download=file_obj["url_private_download"],
            size=file_obj["size"],
            filetype=file_obj.get("filetype", ""),
        )
        result = await download_and_forward_file(
            file_info=file_info,
            channel_id=channel_id,
            bot_token=bot_token,
            rag_client=rag_client,
        )
        if result.get("status") == "ingested":
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=event.get("event_ts", ""),
                text=f"Ingested `{file_info.name}` ({result.get('chunks', 0)} chunks indexed).",
            )
    except Exception as exc:
        logger.error("events.file_ingest_failed", file_id=file_id, error=str(exc))


async def _process_mention(
    event: dict,
    client,
    rag_client: RAGIngestionClient,
    orch_client: OrchestratorClient,
) -> None:
    """Parse @mention query, index question, query orchestrator, reply in thread."""
    channel = event.get("channel", "")
    thread_ts = event.get("ts", "")
    user_id = event.get("user", "")
    raw_text = event.get("text", "")
    query = _strip_mention(raw_text)

    # Always index the question
    await rag_client.index_message(
        text=raw_text,
        author=user_id,
        channel_id=channel,
        timestamp=thread_ts,
        thread_ts=event.get("thread_ts"),
    )

    if not query.strip():
        await reply_in_thread(
            client, channel, thread_ts,
            "Please include a question after mentioning me.",
        )
        return

    # Map the committee channel to its department so e.g. #risk-committee is
    # answered by the Risk agent without needing a [risk] prefix.
    channel_dept = await _resolve_channel_dept(client, channel)

    result = await orch_client.query(
        query=query,
        user_id=user_id,
        channel=channel,
        thread_ts=thread_ts,
        channel_dept=channel_dept,
    )

    if result.error:
        await post_error_to_thread(client, channel, thread_ts, RuntimeError(result.error))
    else:
        await reply_in_thread(client, channel, thread_ts, result)


def _strip_mention(text: str) -> str:
    """Remove leading <@UXXXXXXX> mention token from text."""
    return re.sub(r"^<@[A-Z0-9]+>\s*", "", text).strip()
