"""Tests for the eval runner scoring logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.runner import run_eval


def _make_golden(
    id: str = "ga_test_001",
    question: str = "What is the LCR?",
    expected_answer: str = "The LCR is 130%.",
    acceptable_keywords: list | None = None,
    unacceptable_keywords: list | None = None,
    expected_citations: list | None = None,
) -> dict:
    return {
        "id": id,
        "question": question,
        "expected_answer": expected_answer,
        "acceptable_keywords": acceptable_keywords or [],
        "unacceptable_keywords": unacceptable_keywords or [],
        "expected_citations": expected_citations or [],
    }


def _mock_db_pool():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": 1})
    pool.execute = AsyncMock()
    return pool


class TestRunnerScoring:
    """Test scoring logic in run_eval."""

    @pytest.mark.asyncio
    async def test_unknown_dept_returns_error(self):
        pool = _mock_db_pool()
        result = await run_eval("unknown_dept", [], pool)
        assert "error" in result
        assert "Unknown dept" in result["error"]

    @pytest.mark.asyncio
    async def test_high_similarity_passes(self):
        golden = [_make_golden(expected_answer="The LCR is 130%.")]
        pool = _mock_db_pool()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "The LCR is 130%.",
            "citations": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await run_eval("cac", golden, pool)

        assert result["total"] == 1
        assert result["passed"] == 1
        assert result["accuracy"] == 1.0
        assert result["results"][0]["answer_score"] == 1.0
        assert result["results"][0]["passed"] is True

    @pytest.mark.asyncio
    async def test_low_similarity_fails(self):
        golden = [_make_golden(expected_answer="The LCR is 130%.")]
        pool = _mock_db_pool()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "I cannot help with that request.",
            "citations": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await run_eval("cac", golden, pool)

        assert result["total"] == 1
        assert result["passed"] == 0
        assert result["results"][0]["passed"] is False

    @pytest.mark.asyncio
    async def test_keyword_check_passes(self):
        golden = [
            _make_golden(
                expected_answer="The LCR is 130%.",
                acceptable_keywords=["LCR"],
            )
        ]
        pool = _mock_db_pool()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "The LCR is currently at 130%.",
            "citations": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await run_eval("cac", golden, pool)

        assert result["results"][0]["keywords_present"] is True

    @pytest.mark.asyncio
    async def test_unacceptable_keyword_fails(self):
        golden = [
            _make_golden(
                expected_answer="The LCR is 130%.",
                unacceptable_keywords=["guaranteed"],
            )
        ]
        pool = _mock_db_pool()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "The LCR is guaranteed to be 130%.",
            "citations": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await run_eval("cac", golden, pool)

        assert result["results"][0]["keywords_absent"] is False
        assert result["results"][0]["passed"] is False

    @pytest.mark.asyncio
    async def test_citation_check(self):
        golden = [
            _make_golden(
                expected_answer="The LCR is 130%.",
                expected_citations=["alco_tracker"],
            )
        ]
        pool = _mock_db_pool()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "The LCR is 130%.",
            "citations": ["alco_tracker_2024.xlsx"],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await run_eval("cac", golden, pool)

        assert result["results"][0]["citation_correct"] is True

    @pytest.mark.asyncio
    async def test_http_error_handled(self):
        golden = [_make_golden()]
        pool = _mock_db_pool()

        with patch("src.runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await run_eval("cac", golden, pool)

        assert result["total"] == 1
        assert result["passed"] == 0
        assert "error" in result["results"][0]

    @pytest.mark.asyncio
    async def test_multiple_golden_answers(self):
        golden = [
            _make_golden(id="ga_test_001", expected_answer="Answer one."),
            _make_golden(id="ga_test_002", expected_answer="Answer two."),
            _make_golden(id="ga_test_003", expected_answer="Answer three."),
        ]
        pool = _mock_db_pool()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "Answer one.",
            "citations": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.runner.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await run_eval("cac", golden, pool)

        assert result["total"] == 3
        # First one should pass (exact match), others may not
        assert result["results"][0]["passed"] is True
