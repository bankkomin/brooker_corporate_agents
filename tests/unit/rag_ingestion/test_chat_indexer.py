# tests/unit/rag_ingestion/test_chat_indexer.py
"""Tests for chat indexer."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from services.rag_ingestion.src.chat_indexer import ChatIndexer


@pytest.fixture
def mock_embedder() -> AsyncMock:
    e = AsyncMock()
    e.embed_single.return_value = [0.1] * 4
    return e


@pytest.fixture
def mock_store() -> AsyncMock:
    s = AsyncMock()
    s.search.return_value = []
    s.upsert_chunks.return_value = 1
    return s


@pytest.fixture
def indexer(mock_embedder: AsyncMock, mock_store: AsyncMock) -> ChatIndexer:
    return ChatIndexer(embedder=mock_embedder, store=mock_store)


class TestMakeMessageId:
    def test_deterministic(self) -> None:
        id1 = ChatIndexer.make_message_id("C123", "1234567890.123")
        id2 = ChatIndexer.make_message_id("C123", "1234567890.123")
        assert id1 == id2

    def test_different_channel_different_id(self) -> None:
        id1 = ChatIndexer.make_message_id("C123", "1234567890.123")
        id2 = ChatIndexer.make_message_id("C456", "1234567890.123")
        assert id1 != id2

    def test_length_32(self) -> None:
        msg_id = ChatIndexer.make_message_id("C123", "ts")
        assert len(msg_id) == 32


class TestIndexMessage:
    async def test_indexes_new_message(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        msg_id = await indexer.index_message(
            text="Hello team",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123",
        )
        assert len(msg_id) == 32
        mock_store.upsert_chunks.assert_called_once()

    async def test_skips_duplicate(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        mock_store.search.return_value = [{"message_id": "existing"}]
        msg_id = await indexer.index_message(
            text="Hello team",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123",
        )
        assert len(msg_id) == 32
        mock_store.upsert_chunks.assert_not_called()

    async def test_empty_text_returns_empty(self, indexer: ChatIndexer) -> None:
        msg_id = await indexer.index_message(
            text="",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123",
        )
        assert msg_id == ""

    async def test_whitespace_only_returns_empty(
        self, indexer: ChatIndexer, mock_store: AsyncMock
    ) -> None:
        msg_id = await indexer.index_message(
            text="   ",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.123",
        )
        assert msg_id == ""
        mock_store.upsert_chunks.assert_not_called()

    async def test_thread_ts_preserved(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        await indexer.index_message(
            text="Reply in thread",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.456",
            thread_ts="1234567890.123",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["thread_ts"] == "1234567890.123"

    async def test_thread_ts_none_stored_as_empty_string(
        self, indexer: ChatIndexer, mock_store: AsyncMock
    ) -> None:
        await indexer.index_message(
            text="Top-level message",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.789",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["thread_ts"] == ""

    async def test_dept_metadata(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        await indexer.index_message(
            text="Finance update",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.789",
            dept="FINANCE",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["dept"] == "FINANCE"

    async def test_default_dept_is_cac(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        await indexer.index_message(
            text="General update",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.001",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["dept"] == "CAC"

    async def test_upsert_uses_chat_collection(
        self, indexer: ChatIndexer, mock_store: AsyncMock
    ) -> None:
        await indexer.index_message(
            text="Hello",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.002",
        )
        call_args = mock_store.upsert_chunks.call_args
        assert call_args.kwargs["collection"] == "cac_chat"

    async def test_search_uses_chat_collection(
        self, indexer: ChatIndexer, mock_store: AsyncMock
    ) -> None:
        await indexer.index_message(
            text="Hello",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.003",
        )
        call_args = mock_store.search.call_args
        assert call_args.kwargs["collection"] == "cac_chat"

    async def test_message_id_in_metadata(
        self, indexer: ChatIndexer, mock_store: AsyncMock
    ) -> None:
        msg_id = await indexer.index_message(
            text="Check metadata",
            author="U789",
            channel_id="C456",
            timestamp="1234567890.004",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["message_id"] == msg_id

    async def test_author_in_metadata(self, indexer: ChatIndexer, mock_store: AsyncMock) -> None:
        await indexer.index_message(
            text="Author check",
            author="U999",
            channel_id="C456",
            timestamp="1234567890.005",
        )
        call_args = mock_store.upsert_chunks.call_args
        metadata = call_args.kwargs["metadatas"][0]
        assert metadata["author"] == "U999"

    async def test_embed_single_called_with_text(
        self, indexer: ChatIndexer, mock_embedder: AsyncMock
    ) -> None:
        await indexer.index_message(
            text="Embed me",
            author="U123",
            channel_id="C456",
            timestamp="1234567890.006",
        )
        mock_embedder.embed_single.assert_called_once_with("Embed me")
