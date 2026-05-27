"""Unit tests for the nightly synthesis-scan trigger."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from src.synthesis_scan_trigger import trigger_synthesis_scan


class _MockResponse:
    def __init__(self, status_code: int = 200, body=None, raw_text: str = ""):
        self.status_code = status_code
        self._body = body
        self.text = raw_text or (str(body) if body else "")

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


@pytest.mark.asyncio
async def test_trigger_returns_body_on_success():
    body = {"status": "ok", "candidates": 4, "proposed": 3, "proposal_ids": ["a", "b", "c"]}
    async def _post(self, url, **kw):
        return _MockResponse(200, body)
    with patch("httpx.AsyncClient.post", new=_post):
        result = await trigger_synthesis_scan(
            rag_ingestion_url="http://rag-ingestion:3004", timeout_seconds=30,
        )
    assert result == body


@pytest.mark.asyncio
async def test_trigger_handles_http_error():
    async def _post(self, url, **kw):
        return _MockResponse(500, raw_text="boom")
    with patch("httpx.AsyncClient.post", new=_post):
        result = await trigger_synthesis_scan(
            rag_ingestion_url="http://rag-ingestion:3004", timeout_seconds=30,
        )
    assert result["status"] == "failed"
    assert "http_500" in result["reason"]
    assert result["body"] == "boom"


@pytest.mark.asyncio
async def test_trigger_handles_network_error():
    async def _post(self, url, **kw):
        raise httpx.ConnectError("DNS lookup failed")
    with patch("httpx.AsyncClient.post", new=_post):
        result = await trigger_synthesis_scan(
            rag_ingestion_url="http://nowhere:9999", timeout_seconds=1,
        )
    assert result["status"] == "failed"
    assert result["reason"] == "network_error"


@pytest.mark.asyncio
async def test_trigger_handles_bad_json():
    async def _post(self, url, **kw):
        return _MockResponse(200, body=None, raw_text="not json")
    with patch("httpx.AsyncClient.post", new=_post):
        result = await trigger_synthesis_scan(
            rag_ingestion_url="http://rag-ingestion:3004", timeout_seconds=30,
        )
    assert result["status"] == "failed"
    assert result["reason"] == "bad_json"


@pytest.mark.asyncio
async def test_trigger_strips_trailing_slash_in_url():
    captured_url = []
    async def _post(self, url, **kw):
        captured_url.append(url)
        return _MockResponse(200, {"status": "ok"})
    with patch("httpx.AsyncClient.post", new=_post):
        await trigger_synthesis_scan(
            rag_ingestion_url="http://rag-ingestion:3004/", timeout_seconds=30,
        )
    assert captured_url == ["http://rag-ingestion:3004/synthesis/scan"]
