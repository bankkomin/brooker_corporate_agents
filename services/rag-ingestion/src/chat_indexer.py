# services/rag-ingestion/src/chat_indexer.py
"""Slack message indexer — embeds and stores messages in dept-specific chat collections."""
from __future__ import annotations

import hashlib

import structlog

from .embedder import Embedder
from .qdrant_store import QdrantStore

logger = structlog.get_logger("rag-ingestion.chat_indexer")


class ChatIndexer:
    """Indexes Slack messages into dept-specific Qdrant chat collections."""

    def __init__(self, embedder: Embedder, store: QdrantStore) -> None:
        self._embedder = embedder
        self._store = store

    @staticmethod
    def _collection_for_dept(dept: str) -> str:
        """Return the chat collection name for a department."""
        return f"{dept.lower()}_chat"

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
        dept: str = "cac",
    ) -> str:
        """Embed and store a message. Returns message_id."""
        if not text.strip():
            logger.debug("chat_indexer.empty_text", channel=channel_id)
            return ""

        collection = self._collection_for_dept(dept)
        message_id = self.make_message_id(channel_id, timestamp)

        # Embed once (used for both dedup check and upsert)
        vector = await self._embedder.embed_single(text)

        # Check for existing point (dedup via metadata filter, no extra embedding)
        existing = await self._store.search(
            collection=collection,
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
            collection=collection,
            texts=[text],
            vectors=[vector],
            metadatas=[metadata],
        )
        logger.info("chat_indexer.indexed", message_id=message_id, collection=collection)
        return message_id
