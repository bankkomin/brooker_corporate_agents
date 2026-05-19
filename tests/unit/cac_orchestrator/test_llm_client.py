"""Unit tests for LLMClient (Google GenAI SDK)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.cac_orchestrator.src.tools.llm_client import LLMClient
from tenacity import RetryError


@pytest.fixture
def mock_genai_client():
    """Patch genai.Client so no real credentials are needed."""
    with patch("services.cac_orchestrator.src.tools.llm_client.genai.Client") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.aio = MagicMock()
        mock_instance.aio.models = MagicMock()
        mock_instance.aio.models.generate_content = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def llm_client(mock_genai_client) -> LLMClient:
    """Return an LLMClient with a mocked genai.Client."""
    return LLMClient(model="gemini-3.1-flash-lite-preview", timeout=5.0)


def _make_genai_response(text: str, prompt_tokens: int = 10, output_tokens: int = 20):
    """Build a mock generate_content response."""
    resp = MagicMock()
    resp.text = text
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = output_tokens
    resp.usage_metadata = usage
    return resp


@pytest.mark.asyncio
async def test_chat_sends_correct_request(
    llm_client: LLMClient, mock_genai_client: MagicMock
) -> None:
    """Verify generate_content is called with converted Gemini contents."""
    mock_genai_client.aio.models.generate_content.return_value = _make_genai_response("Hello!")

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hi"},
    ]
    await llm_client.chat(messages, temperature=0.2, max_tokens=512)

    mock_genai_client.aio.models.generate_content.assert_awaited_once()
    call_kwargs = mock_genai_client.aio.models.generate_content.call_args[1]
    assert call_kwargs["model"] == "gemini-3.1-flash-lite-preview"
    # System message becomes system_instruction in config
    assert call_kwargs["config"].system_instruction == "You are helpful."
    # User message becomes a Content with role "user"
    contents = call_kwargs["contents"]
    assert len(contents) == 1
    assert contents[0].role == "user"


@pytest.mark.asyncio
async def test_chat_returns_content(
    llm_client: LLMClient, mock_genai_client: MagicMock
) -> None:
    """Verify response text is returned from generate_content."""
    mock_genai_client.aio.models.generate_content.return_value = _make_genai_response(
        "The answer is 42."
    )

    result = await llm_client.chat([{"role": "user", "content": "What is the answer?"}])
    assert result == "The answer is 42."


@pytest.mark.asyncio
async def test_chat_retries_on_exception(
    llm_client: LLMClient, mock_genai_client: MagicMock
) -> None:
    """Verify that an exception causes retry and eventually succeeds."""
    mock_genai_client.aio.models.generate_content.side_effect = [
        RuntimeError("transient error"),
        _make_genai_response("Retry worked!"),
    ]

    result = await llm_client.chat([{"role": "user", "content": "retry test"}])
    assert result == "Retry worked!"
    assert mock_genai_client.aio.models.generate_content.await_count == 2


@pytest.mark.asyncio
async def test_chat_raises_after_all_retries(
    llm_client: LLMClient, mock_genai_client: MagicMock
) -> None:
    """Verify that persistent errors propagate after retries are exhausted."""
    mock_genai_client.aio.models.generate_content.side_effect = RuntimeError("persistent error")

    with pytest.raises(RetryError):
        await llm_client.chat([{"role": "user", "content": "error test"}])


@pytest.mark.asyncio
async def test_close_is_noop(
    llm_client: LLMClient, mock_genai_client: MagicMock
) -> None:
    """Verify close() completes without error (no persistent connection in genai SDK)."""
    await llm_client.close()  # should not raise
