"""Integration test: escalation flow — agent -> escalation -> email notification."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.cac_orchestrator.src.nodes.escalation_check import escalation_check
from services.cac_orchestrator.src.nodes.notify_escalation import notify_escalation


@pytest.fixture
def escalation_rules(tmp_path):
    rules = {
        "triggers": [
            {
                "type": "covenant_ratio",
                "threshold": 4.0,
                "condition": ">",
                "description": "Net Debt/EBITDA covenant breach",
            },
        ]
    }
    rules_file = tmp_path / "escalation_rules.json"
    rules_file.write_text(json.dumps(rules))
    return str(rules_file)


@pytest.mark.asyncio
async def test_escalation_triggers_and_notifies(escalation_rules: str) -> None:
    """Agent response mentioning covenant_ratio 4.2 triggers escalation and email."""
    state = {
        "agent_response": (
            "The covenant ratio has increased to 4.2 net debt/EBITDA,"
            " breaching the 4.0 limit."
        ),
        "agent_name": "funding-agent",
        "query": "check covenants",
        "user_id": "U123",
        "channel": "C-cac",
    }

    # Step 1: escalation_check detects breach
    result = await escalation_check(state, rules_path=escalation_rules)
    assert result["escalation_triggered"] is True
    assert "4.2" in result["escalation_detail"]

    # Step 2: merge result into state
    state.update(result)

    # Step 3: notify_escalation fires POST
    with patch(
        "services.cac_orchestrator.src.nodes.notify_escalation.httpx.AsyncClient"
    ) as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        notify_result = await notify_escalation(
            state, email_notifier_url="http://email-notifier:3005"
        )
        assert notify_result == {}

        call_args = mock_client.post.call_args
        assert "/notify/escalation" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["agent_name"] == "funding-agent"


@pytest.mark.asyncio
async def test_no_escalation_when_below_threshold(escalation_rules: str) -> None:
    """Agent response with covenant_ratio 3.5 does NOT trigger escalation."""
    state = {
        "agent_response": "The covenant ratio is 3.5, well within the 4.0 limit.",
    }
    result = await escalation_check(state, rules_path=escalation_rules)
    assert result["escalation_triggered"] is False


@pytest.mark.asyncio
async def test_escalation_does_not_block_pipeline(escalation_rules: str) -> None:
    """Escalation notification failure does not block the pipeline."""
    state = {
        "escalation_triggered": True,
        "escalation_detail": "test breach",
        "agent_name": "test",
        "query": "test",
        "user_id": "U123",
        "channel": "C-test",
    }
    with patch(
        "services.cac_orchestrator.src.nodes.notify_escalation.httpx.AsyncClient"
    ) as mock_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = ConnectionError("email-notifier down")
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await notify_escalation(
            state, email_notifier_url="http://email-notifier:3005"
        )
        assert result == {}
