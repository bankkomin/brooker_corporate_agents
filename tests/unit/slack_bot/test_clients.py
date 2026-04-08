"""Tests for HTTP client wrappers."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


class TestRAGIngestionClient:
    @pytest.mark.asyncio
    async def test_index_message_posts_correct_payload(self) -> None:
        from services.slack_bot.src.clients import RAGIngestionClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"indexed": True, "message_id": "msg_abc"}

        http = MagicMock()
        http.post = AsyncMock(return_value=mock_response)

        client = RAGIngestionClient(http=http, base_url="http://rag:3004")
        result = await client.index_message(
            text="Q3 update",
            author="U12345",
            channel_id="C123",
            timestamp="1711234567.000100",
        )
        assert result is True
        call_kwargs = http.post.call_args
        assert "/ingest/message" in call_kwargs[0][0]

    @pytest.mark.asyncio
    async def test_index_message_returns_false_on_error(self) -> None:
        from services.slack_bot.src.clients import RAGIngestionClient

        http = MagicMock()
        http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        client = RAGIngestionClient(http=http, base_url="http://rag:3004")
        result = await client.index_message(
            text="test", author="U1", channel_id="C1", timestamp="1.0",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self) -> None:
        from services.slack_bot.src.clients import RAGIngestionClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        http = MagicMock()
        http.get = AsyncMock(return_value=mock_resp)

        client = RAGIngestionClient(http=http, base_url="http://rag:3004")
        assert await client.health_check() is True


class TestOrchestratorClient:
    @pytest.mark.asyncio
    async def test_query_when_disabled_returns_stub(self) -> None:
        from services.slack_bot.src.clients import OrchestratorClient

        http = MagicMock()
        client = OrchestratorClient(http=http, base_url="http://orch:3001", enabled=False)
        result = await client.query(
            query="What is the LCR?",
            user_id="U123",
            channel_id="C123",
        )
        assert "still being set up" in result.answer.lower() or "not yet" in result.answer.lower()
        http.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_when_enabled_calls_orchestrator(self) -> None:
        from services.slack_bot.src.clients import OrchestratorClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "answer": "LCR is 135%",
            "citations": [],
            "confidence": 0.91,
        }

        http = MagicMock()
        http.post = AsyncMock(return_value=mock_resp)

        client = OrchestratorClient(http=http, base_url="http://orch:3001", enabled=True)
        result = await client.query(
            query="What is the LCR?",
            user_id="U123",
            channel_id="C123",
        )
        assert "135%" in result.answer
        http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_error_returns_error_response(self) -> None:
        from services.slack_bot.src.clients import OrchestratorClient

        http = MagicMock()
        http.post = AsyncMock(side_effect=httpx.ConnectError("down"))

        client = OrchestratorClient(http=http, base_url="http://orch:3001", enabled=True)
        result = await client.query(
            query="test", user_id="U1", channel_id="C1",
        )
        assert result.error is not None
