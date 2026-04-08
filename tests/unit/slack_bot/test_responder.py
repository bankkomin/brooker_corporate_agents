"""Tests for slack-bot response formatting and thread replies."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestFormatQueryResponse:
    def test_plain_answer_returns_text(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(answer="LCR is 135%.", confidence=0.91)
        text, blocks = format_response(r)
        assert "LCR is 135%" in text

    def test_with_citations_includes_sources(self) -> None:
        from services.slack_bot.src.models import Citation, QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(
            answer="Rate is 3.15%",
            citations=[Citation(source="ALCO_Tracker.xlsx", excerpt="Row 8 col E", score=0.95)],
            confidence=0.91,
        )
        text, blocks = format_response(r)
        assert blocks is not None
        block_text = str(blocks)
        assert "ALCO_Tracker.xlsx" in block_text

    def test_no_citations_returns_none_blocks(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(answer="No data found.", confidence=0.91)
        text, blocks = format_response(r)
        assert blocks is None or all(
            b.get("type") != "context" or "Sources" not in str(b) for b in blocks
        )

    def test_error_response_shows_error(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(answer="", error="Service unavailable")
        text, blocks = format_response(r)
        assert "error" in text.lower() or "unavailable" in text.lower()

    def test_citation_excerpt_truncated(self) -> None:
        from services.slack_bot.src.models import Citation, QueryResponse
        from services.slack_bot.src.responder import format_response

        long_excerpt = "A" * 200
        r = QueryResponse(
            answer="Answer",
            citations=[Citation(source="doc.pdf", excerpt=long_excerpt, score=0.9)],
            confidence=0.91,
        )
        _, blocks = format_response(r)
        block_text = str(blocks)
        assert len(long_excerpt) > 120
        # The full 200-char excerpt should not appear untruncated
        assert long_excerpt not in block_text


class TestReplyInThread:
    @pytest.mark.asyncio
    async def test_posts_to_correct_channel(self) -> None:
        from services.slack_bot.src.responder import reply_in_thread

        client = MagicMock()
        client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "9999.0"})
        await reply_in_thread(client, "C123", "1234.5678", "Hello")
        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["thread_ts"] == "1234.5678"

    @pytest.mark.asyncio
    async def test_query_response_uses_blocks(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import reply_in_thread

        client = MagicMock()
        client.chat_postMessage = AsyncMock(return_value={"ok": True})
        resp = QueryResponse(answer="Answer here", confidence=0.9)
        await reply_in_thread(client, "C123", "1234.5678", resp)
        call_kwargs = client.chat_postMessage.call_args[1]
        assert "text" in call_kwargs


class TestPostErrorToThread:
    @pytest.mark.asyncio
    async def test_sends_user_friendly_message(self) -> None:
        from services.slack_bot.src.responder import post_error_to_thread

        client = MagicMock()
        client.chat_postMessage = AsyncMock(return_value={"ok": True})
        await post_error_to_thread(client, "C123", "1234.5678", RuntimeError("db crash"))
        call_kwargs = client.chat_postMessage.call_args[1]
        # Should NOT contain the raw exception message
        assert "db crash" not in call_kwargs["text"]
        # Should contain user-friendly language
        assert "error" in call_kwargs["text"].lower() or "sorry" in call_kwargs["text"].lower()
