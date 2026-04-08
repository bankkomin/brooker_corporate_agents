"""Unit tests for escalation_check node."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from services.cac_orchestrator.src.nodes.escalation_check import escalation_check

_RULES = {
    "triggers": [
        {
            "type": "covenant_ratio",
            "threshold": 3.5,
            "condition": ">",
            "severity": "high",
            "description": "Covenant ratio exceeded",
        },
        {
            "type": "liquidity_ratio",
            "threshold": 0.5,
            "condition": "<",
            "severity": "critical",
            "description": "Liquidity ratio critically low",
        },
    ]
}


@pytest.fixture
def rules_path(tmp_path: Path) -> str:
    p = tmp_path / "escalation_rules.json"
    p.write_text(json.dumps(_RULES), encoding="utf-8")
    return str(p)


async def test_covenant_ratio_above_threshold_triggers(rules_path: str) -> None:
    """Value 3.6 > 3.5 covenant threshold triggers escalation."""
    state = {"agent_response": "The covenant ratio stands at 3.6 this quarter."}
    result = await escalation_check(state, rules_path=rules_path)
    assert result["escalation_triggered"] is True
    assert result["escalation_detail"] is not None
    assert "3.6" in result["escalation_detail"]


async def test_liquidity_ratio_below_threshold_triggers(rules_path: str) -> None:
    """Value 0.4 < 0.5 liquidity threshold triggers escalation."""
    state = {"agent_response": "Current liquidity ratio is 0.4, which is below minimum."}
    result = await escalation_check(state, rules_path=rules_path)
    assert result["escalation_triggered"] is True
    assert result["escalation_detail"] is not None
    assert "0.4" in result["escalation_detail"]


async def test_normal_values_no_escalation(rules_path: str) -> None:
    """Values within safe range do not trigger escalation."""
    state = {
        "agent_response": (
            "Covenant ratio is 2.1, well within limits. Liquidity ratio is 0.8."
        )
    }
    result = await escalation_check(state, rules_path=rules_path)
    assert result["escalation_triggered"] is False
    assert result["escalation_detail"] is None


async def test_no_matching_keywords_no_escalation(rules_path: str) -> None:
    """Response about unrelated topic does not trigger escalation."""
    state = {"agent_response": "The board meeting was held on Monday."}
    result = await escalation_check(state, rules_path=rules_path)
    assert result["escalation_triggered"] is False
    assert result["escalation_detail"] is None


async def test_missing_rules_file_no_escalation(tmp_path: Path) -> None:
    """Non-existent rules file handled gracefully — no escalation."""
    bad_path = str(tmp_path / "nonexistent.json")
    state = {"agent_response": "covenant ratio 5.0"}
    result = await escalation_check(state, rules_path=bad_path)
    assert result["escalation_triggered"] is False
    assert result["escalation_detail"] is None


async def test_escalation_detail_format(rules_path: str) -> None:
    """escalation_detail includes the extracted value and threshold."""
    state = {"agent_response": "The covenant ratio is now 4.2."}
    result = await escalation_check(state, rules_path=rules_path)
    assert result["escalation_triggered"] is True
    detail = result["escalation_detail"]
    assert detail is not None
    # Must mention the value and the threshold
    assert "4.2" in detail
    assert "3.5" in detail
