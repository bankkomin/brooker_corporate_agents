"""Bolt event handler registrations."""
from __future__ import annotations

import asyncio
import re

import structlog
from slack_bolt.async_app import AsyncApp

from .clients import OrchestratorClient, RAGIngestionClient
from .file_handler import download_and_forward_file
from .image_intent import ImagePlacementSpec, extract_image_placement
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
                _process_mention(event, client, rag_client, orch_client, bot_token)
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


async def _collect_image_uploads(
    event: dict,
    bot_token: str,
    rag_client: RAGIngestionClient,
    channel_id: str,
) -> list[dict]:
    """Download any image attachments from the event and upload them to MinIO.

    Iterates over ``event["files"]`` (present when a user attaches files to an
    @mention). Documents are forwarded to rag-ingestion as a side-effect; only
    image results (status == "uploaded_image") are returned for deck embedding.

    MinIO failures per file are caught and logged — they do NOT abort the whole
    request.  Other file types (pdf, xlsx, …) are forwarded to rag-ingestion
    but are not included in the returned list.
    """
    raw_files: list[dict] = event.get("files") or []
    if not raw_files:
        return []

    image_uploads: list[dict] = []

    for file_obj in raw_files:
        file_id: str = file_obj.get("id", "")
        try:
            file_info = SlackFileInfo(
                id=file_id,
                name=file_obj.get("name", ""),
                mimetype=file_obj.get("mimetype", ""),
                url_private_download=file_obj.get("url_private_download", ""),
                size=file_obj.get("size", 0),
                filetype=file_obj.get("filetype", ""),
            )
        except Exception as exc:
            logger.warning(
                "events.file_info_parse_error",
                file_id=file_id,
                error=str(exc),
            )
            continue

        try:
            result = await download_and_forward_file(
                file_info=file_info,
                channel_id=channel_id,
                bot_token=bot_token,
                rag_client=rag_client,
            )
        except Exception as exc:
            # MinIO down, network failure, etc. — log and skip this image.
            logger.error(
                "events.file_upload_failed",
                file_id=file_id,
                filename=file_info.name,
                error=str(exc),
            )
            continue

        if result.get("status") == "uploaded_image":
            image_uploads.append(
                {
                    "minio_key": result["minio_key"],
                    "filename": result["filename"],
                    "file_id": result["file_id"],
                    "channel_id": channel_id,
                }
            )
            logger.info(
                "events.image_collected",
                file_id=file_id,
                minio_key=result["minio_key"],
            )

    return image_uploads


async def _process_mention(
    event: dict,
    client,
    rag_client: RAGIngestionClient,
    orch_client: OrchestratorClient,
    bot_token: str = "",
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

    # ------------------------------------------------------------------
    # Collect image uploads attached to this @mention (if any).
    # We do this regardless of intent so documents always get indexed too.
    # ------------------------------------------------------------------
    image_uploads: list[dict] = []
    if event.get("files") and bot_token:
        image_uploads = await _collect_image_uploads(
            event=event,
            bot_token=bot_token,
            rag_client=rag_client,
            channel_id=channel,
        )

    # ------------------------------------------------------------------
    # Determine intent so we know whether to run the image extractor.
    # We mirror the routing logic from OrchestratorClient._parse_dept so
    # we can decide *here* before the client call.  The client will still
    # do its own routing internally.
    # ------------------------------------------------------------------
    images_spec: list[ImagePlacementSpec] = []
    if image_uploads:
        # Peek at the intent: explicit [dept] prefix or LLM classification.
        dept_hint = _extract_explicit_dept(query)
        is_artefact = dept_hint in ("deck", "report") or (
            dept_hint is None
            and await _intent_is_artefact(orch_client, query)
        )
        if is_artefact:
            artefact_kind = "report" if dept_hint == "report" else "deck"
            try:
                images_spec = await extract_image_placement(
                    message_text=query,
                    image_uploads=image_uploads,
                    artefact_kind=artefact_kind,
                )
                logger.info(
                    "events.image_placement_extracted",
                    n_specs=len(images_spec),
                    artefact_kind=artefact_kind,
                )
            except Exception as exc:
                # Extractor failure must never kill the whole request.
                logger.error(
                    "events.image_placement_failed",
                    error=str(exc),
                    fallback="no_images",
                )
                images_spec = []

    result = await orch_client.query(
        query=query,
        user_id=user_id,
        channel=channel,
        thread_ts=thread_ts,
        channel_dept=channel_dept,
        images=images_spec,
    )

    if result.error:
        await post_error_to_thread(client, channel, thread_ts, RuntimeError(result.error))
    else:
        await reply_in_thread(client, channel, thread_ts, result)


# ---------------------------------------------------------------------------
# Intent-peek helpers (used only by _process_mention to decide image routing)
# ---------------------------------------------------------------------------

_EXPLICIT_DEPT_RE = re.compile(r"^\s*\[([a-z]+)\]\s*", re.IGNORECASE)
_ARTEFACT_DEPTS = frozenset({"deck", "report"})


def _extract_explicit_dept(query: str) -> str | None:
    """Return the [dept] prefix value if present and it's an artefact dept."""
    m = _EXPLICIT_DEPT_RE.match(query)
    if m:
        d = m.group(1).lower()
        if d in _ARTEFACT_DEPTS:
            return d
    return None


async def _intent_is_artefact(orch_client: OrchestratorClient, query: str) -> bool:
    """Ask the intent router if this message is a deck request.

    Returns False on any error — we'd rather skip image embedding than crash.
    """
    try:
        intent = await orch_client._intent_router.classify(query)
        return intent.name == "deck"
    except Exception as exc:
        logger.warning("events.intent_peek_failed", error=str(exc))
        return False


def _strip_mention(text: str) -> str:
    """Remove leading <@UXXXXXXX> mention token from text."""
    return re.sub(r"^<@[A-Z0-9]+>\s*", "", text).strip()
