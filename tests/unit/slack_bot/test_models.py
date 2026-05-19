"""Tests for slack-bot Pydantic models."""

import pytest
from pydantic import ValidationError


class TestSlackFileInfo:
    def test_valid_file_info(self) -> None:
        from services.slack_bot.src.models import SlackFileInfo

        f = SlackFileInfo(
            id="F12345",
            name="alco_minutes.pdf",
            mimetype="application/pdf",
            url_private_download="https://files.slack.com/files/alco_minutes.pdf",
            size=204800,
            filetype="pdf",
        )
        assert f.id == "F12345"
        assert f.size == 204800

    def test_missing_id_raises(self) -> None:
        from services.slack_bot.src.models import SlackFileInfo

        with pytest.raises(ValidationError):
            SlackFileInfo(
                name="test.pdf",
                mimetype="application/pdf",
                url_private_download="https://example.com/file",
                size=100,
                filetype="pdf",
            )


class TestIngestMessageRequest:
    def test_valid_request(self) -> None:
        from services.slack_bot.src.models import IngestMessageRequest

        req = IngestMessageRequest(
            text="Q3 funding update",
            author="U12345",
            channel_id="C0123456789",
            timestamp="1711234567.000100",
        )
        assert req.dept == "CAC"
        assert req.thread_ts is None

    def test_missing_text_raises(self) -> None:
        from services.slack_bot.src.models import IngestMessageRequest

        with pytest.raises(ValidationError):
            IngestMessageRequest(
                author="U12345",
                channel_id="C0123456789",
                timestamp="1711234567.000100",
            )


class TestQueryRequest:
    def test_valid_query(self) -> None:
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(
            query="What is the current LCR?",
            channel="C0123456789",
            user_id="U12345",
        )
        assert q.thread_ts is None
        assert q.context == {}

    def test_with_thread_ts(self) -> None:
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(
            query="Follow up",
            channel="C123",
            user_id="U456",
            thread_ts="1711234567.000100",
        )
        assert q.thread_ts == "1711234567.000100"


class TestQueryResponse:
    def test_valid_response(self) -> None:
        from services.slack_bot.src.models import QueryResponse

        r = QueryResponse(
            answer="The current LCR is 135%.",
            confidence=0.91,
        )
        assert r.citations == []
        assert r.error is None

    def test_with_citations(self) -> None:
        from services.slack_bot.src.models import Citation, QueryResponse

        r = QueryResponse(
            answer="Rate is 3.15%",
            citations=[Citation(source="ALCO_Tracker.xlsx", excerpt="Row 8", score=0.95)],
            confidence=0.91,
        )
        assert len(r.citations) == 1
        assert r.citations[0].source == "ALCO_Tracker.xlsx"
