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

        # Upsert
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
