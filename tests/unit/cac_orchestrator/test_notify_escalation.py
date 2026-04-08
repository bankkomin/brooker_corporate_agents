"""Tests for notify_escalation node."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.cac_orchestrator.src.nodes.notify_escalation import notify_escalation


@pytest.mark.asyncio
async def test_notify_sends_when_escalation_triggered() -> None:
    state = {
        "escalation_triggered": True,
        "escalation_detail": "Covenant breach: 4.2x > 4.0x",
        "agent_name": "funding-agent",
        "query": "check covenants",
        "user_id": "U123",
        "channel": "C-cac",
    }
    with patch(
        "services.cac_orchestrator.src.nodes.notify_escalation.httpx.AsyncClient"
    ) as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await notify_escalation(
            state, email_notifier_url="http://email-notifier:3005"
        )
        mock_client.post.assert_called_once()
    assert result == {}


@pytest.mark.asyncio
async def test_notify_skips_when_no_escalation() -> None:
    state = {"escalation_triggered": False}
    result = await notify_escalation(
        state, email_notifier_url="http://email-notifier:3005"
    )
    assert result == {}


@pytest.mark.asyncio
async def test_notify_handles_connection_error() -> None:
    state = {
        "escalation_triggered": True,
        "escalation_detail": "test",
        "agent_name": "test",
        "query": "test",
        "user_id": "U123",
        "channel": "C-test",
    }
    with patch(
        "services.cac_orchestrator.src.nodes.notify_escalation.httpx.AsyncClient"
    ) as mock_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await notify_escalation(
            state, email_notifier_url="http://email-notifier:3005"
        )
    assert result == {}
