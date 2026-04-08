"""Unit tests for LLMClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from services.cac_orchestrator.src.tools.llm_client import LLMClient


@pytest.fixture
def llm_client() -> LLMClient:
    return LLMClient(base_url="http://localhost:8000/v1", model="mistral-7b", timeout=5.0)


@pytest.mark.asyncio
async def test_chat_sends_correct_request(llm_client: LLMClient) -> None:
    """Verify POST body has model, messages, temperature, max_tokens."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello!"}}],
        "usage": {"total_tokens": 42},
    }

    with patch.object(llm_client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        messages = [{"role": "user", "content": "Hi"}]
        await llm_client.chat(messages, temperature=0.2, max_tokens=512)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "http://localhost:8000/v1/chat/completions"
        body = call_kwargs[1]["json"]
        assert body["model"] == "mistral-7b"
        assert body["messages"] == messages
        assert body["temperature"] == 0.2
        assert body["max_tokens"] == 512


@pytest.mark.asyncio
async def test_chat_returns_content(llm_client: LLMClient) -> None:
    """Verify content is extracted from choices[0].message.content."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "The answer is 42."}}],
        "usage": {"total_tokens": 10},
    }

    with patch.object(llm_client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await llm_client.chat([{"role": "user", "content": "What is the answer?"}])
        assert result == "The answer is 42."


@pytest.mark.asyncio
async def test_chat_retries_on_connect_error(llm_client: LLMClient) -> None:
    """Verify that ConnectError causes retry and eventually succeeds."""
    success_response = MagicMock()
    success_response.raise_for_status = MagicMock()
    success_response.json.return_value = {
        "choices": [{"message": {"content": "Retry worked!"}}],
        "usage": {"total_tokens": 5},
    }

    with patch.object(
        llm_client._client,
        "post",
        new_callable=AsyncMock,
        side_effect=[httpx.ConnectError("connection refused"), success_response],
    ) as mock_post:
        result = await llm_client.chat([{"role": "user", "content": "retry test"}])
        assert result == "Retry worked!"
        assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_chat_raises_on_http_error(llm_client: LLMClient) -> None:
    """Verify that a 500 HTTP error propagates after retries are exhausted."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=MagicMock(), response=MagicMock()
    )
    mock_response.json.return_value = {}

    with patch.object(llm_client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(httpx.HTTPStatusError):
            await llm_client.chat([{"role": "user", "content": "error test"}])


@pytest.mark.asyncio
async def test_close_calls_aclose(llm_client: LLMClient) -> None:
    """Verify close() calls aclose() on the underlying httpx client."""
    with patch.object(llm_client._client, "aclose", new_callable=AsyncMock) as mock_aclose:
        await llm_client.close()
        mock_aclose.assert_called_once()
