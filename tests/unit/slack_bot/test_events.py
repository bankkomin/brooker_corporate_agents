"""Tests for Bolt event handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_ack_called_immediately(self) -> None:
        from services.slack_bot.src.events import _process_message

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)

        event = {
            "text": "Q3 funding update",
            "user": "U12345",
            "channel": "C123",
            "ts": "1711234567.000100",
        }

        await _process_message(event, mock_rag)
        mock_rag.index_message.assert_called_once()
        call_kwargs = mock_rag.index_message.call_args[1]
        assert call_kwargs["text"] == "Q3 funding update"
        assert call_kwargs["author"] == "U12345"

    @pytest.mark.asyncio
    async def test_empty_text_still_indexes(self) -> None:
        from services.slack_bot.src.events import _process_message

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)

        event = {"text": "", "user": "U1", "channel": "C1", "ts": "1.0"}
        await _process_message(event, mock_rag)
        mock_rag.index_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_rag_error_does_not_raise(self) -> None:
        from services.slack_bot.src.events import _process_message

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=False)

        event = {"text": "test", "user": "U1", "channel": "C1", "ts": "1.0"}
        await _process_message(event, mock_rag)


class TestHandleAppMention:
    @pytest.mark.asyncio
    async def test_queries_orchestrator_and_replies(self) -> None:
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)

        mock_orch = MagicMock()
        mock_orch.query = AsyncMock(
            return_value=QueryResponse(answer="LCR is 135%", confidence=0.91)
        )

        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

        event = {
            "text": "<@U_BOT> What is the LCR?",
            "user": "U12345",
            "channel": "C123",
            "ts": "1711234567.000100",
        }

        await _process_mention(event, mock_client, mock_rag, mock_orch)
        mock_orch.query.assert_called_once()
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["thread_ts"] == "1711234567.000100"

    @pytest.mark.asyncio
    async def test_indexes_question_to_rag(self) -> None:
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)
        mock_orch = MagicMock()
        mock_orch.query = AsyncMock(
            return_value=QueryResponse(answer="answer", confidence=0.9)
        )
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

        event = {
            "text": "<@U_BOT> question",
            "user": "U1",
            "channel": "C1",
            "ts": "1.0",
        }

        await _process_mention(event, mock_client, mock_rag, mock_orch)
        mock_rag.index_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_error_replies_error(self) -> None:
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)
        mock_orch = MagicMock()
        mock_orch.query = AsyncMock(
            return_value=QueryResponse(answer="Error", error="down")
        )
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

        event = {"text": "<@U_BOT> test", "user": "U1", "channel": "C1", "ts": "1.0"}
        await _process_mention(event, mock_client, mock_rag, mock_orch)
        mock_client.chat_postMessage.assert_called_once()


class TestStripMention:
    def test_strips_mention_token(self) -> None:
        from services.slack_bot.src.events import _strip_mention

        assert _strip_mention("<@U12345ABC> What is the LCR?") == "What is the LCR?"

    def test_handles_no_mention(self) -> None:
        from services.slack_bot.src.events import _strip_mention

        assert _strip_mention("plain text") == "plain text"

    def test_handles_empty_after_mention(self) -> None:
        from services.slack_bot.src.events import _strip_mention

        assert _strip_mention("<@U12345ABC>") == ""
