"""Tests for services.shared.vm_bridge — Phase 6.3 venture-monitor integration bridge."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from services.shared.vm_bridge import VentureMonitorBridge


@pytest.fixture()
def bridge():
    return VentureMonitorBridge(base_url="http://test-vm:8000")


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    """Create a mock httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://test-vm:8000"),
    )


# --- get_fund_scores ---


@pytest.mark.asyncio()
async def test_get_fund_scores(bridge):
    mock_data = {"scores": [{"fund_id": 1, "score": 72.5}, {"fund_id": 2, "score": 85.0}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response(mock_data)):
        result = await bridge.get_fund_scores()

    assert len(result) == 2
    assert result[0]["fund_id"] == 1
    assert result[0]["score"] == 72.5


@pytest.mark.asyncio()
async def test_get_fund_scores_empty(bridge):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response({"scores": []})):
        result = await bridge.get_fund_scores()

    assert result == []


# --- get_fund_score ---


@pytest.mark.asyncio()
async def test_get_fund_score(bridge):
    mock_data = {"fund_id": 1, "history": [{"date": "2026-04-01", "score": 72.5}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response(mock_data)):
        result = await bridge.get_fund_score(1)

    assert result["fund_id"] == 1
    assert len(result["history"]) == 1


# --- get_high_severity_signals ---


@pytest.mark.asyncio()
async def test_get_high_severity_signals(bridge):
    mock_data = {
        "signals": [
            {"entity_name": "Fund Alpha", "severity": "high", "description": "NAV drop > 10%", "source": "bloomberg"},
        ],
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response(mock_data)):
        result = await bridge.get_high_severity_signals()

    assert len(result) == 1
    assert result[0]["severity"] == "high"


@pytest.mark.asyncio()
async def test_get_high_severity_signals_empty(bridge):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response({"signals": []})):
        result = await bridge.get_high_severity_signals(min_severity="critical")

    assert result == []


# --- get_fund_briefing ---


@pytest.mark.asyncio()
async def test_get_fund_briefing(bridge):
    mock_data = {"briefings": [{"fund_id": 1, "date": "2026-04-25", "summary": "GP update call notes."}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response(mock_data)):
        result = await bridge.get_fund_briefing(1)

    assert result is not None
    assert result["summary"] == "GP update call notes."


@pytest.mark.asyncio()
async def test_get_fund_briefing_empty(bridge):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response({"briefings": []})):
        result = await bridge.get_fund_briefing(1)

    assert result is None


@pytest.mark.asyncio()
async def test_get_fund_briefing_not_found(bridge):
    resp = httpx.Response(
        status_code=404,
        json={"error": "Not found"},
        request=httpx.Request("GET", "http://test-vm:8000"),
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
        result = await bridge.get_fund_briefing(999)

    assert result is None


# --- search_fund_data ---


@pytest.mark.asyncio()
async def test_search_fund_data(bridge):
    mock_data = {"funds": [{"id": 1, "name": "Alpha Fund"}], "total": 1}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response(mock_data)):
        result = await bridge.search_fund_data("Alpha")

    assert "funds" in result
    assert result["funds"][0]["name"] == "Alpha Fund"


# --- get_reconciliation_summary ---


@pytest.mark.asyncio()
async def test_get_reconciliation_summary(bridge):
    mock_data = {"reconciliations": [{"fund_id": 1, "status": "matched", "last_run": "2026-04-28"}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=_mock_response(mock_data)):
        result = await bridge.get_reconciliation_summary()

    assert len(result) == 1
    assert result[0]["status"] == "matched"


# --- forward_signals_to_slack ---


@pytest.mark.asyncio()
async def test_forward_signals_to_slack(bridge):
    signals = [
        {"entity_name": "Fund Alpha", "severity": "critical", "description": "Major issue", "source": "manual"},
        {"entity_name": "Fund Beta", "severity": "high", "description": "Watch item", "source": "bloomberg"},
    ]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=_mock_response({"ok": True})):
        forwarded = await bridge.forward_signals_to_slack(signals, "https://hooks.slack.com/test")

    assert forwarded == 2


@pytest.mark.asyncio()
async def test_forward_signals_to_slack_partial_failure(bridge):
    signals = [
        {"entity_name": "Fund Alpha", "severity": "critical", "description": "Issue", "source": "manual"},
    ]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("timeout")):
        forwarded = await bridge.forward_signals_to_slack(signals, "https://hooks.slack.com/test")

    assert forwarded == 0


@pytest.mark.asyncio()
async def test_forward_signals_empty(bridge):
    forwarded = await bridge.forward_signals_to_slack([], "https://hooks.slack.com/test")
    assert forwarded == 0


# --- Constructor ---


def test_bridge_strips_trailing_slash():
    b = VentureMonitorBridge(base_url="http://example.com/")
    assert b.base_url == "http://example.com"


def test_bridge_default_url():
    b = VentureMonitorBridge()
    assert b.base_url == "http://localhost:8000"
