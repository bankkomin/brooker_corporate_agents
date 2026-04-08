"""Unit tests for specialist CAC agents."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.cac_orchestrator.src.agents import (
    AlmAgent,
    BaseAgent,
    CapitalAgent,
    FundingAgent,
    LiquidityAgent,
)
from services.cac_orchestrator.src.skills.loader import SkillsLoader
from services.cac_orchestrator.src.tools.llm_client import LLMClient


@pytest.fixture
def mock_llm() -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "analysis": "Test analysis with [Source: test.xlsx]",
                "proposed_change": None,
                "confidence": 0.75,
                "escalation_flags": [],
            }
        )
    )
    return llm


@pytest.fixture
def mock_skills() -> SkillsLoader:
    loader = MagicMock(spec=SkillsLoader)
    loader.load_agent_skills = AsyncMock(return_value="## Mandate\nTest skill content.")
    return loader


@pytest.fixture
def mock_llm_with_proposal() -> LLMClient:
    llm = MagicMock(spec=LLMClient)
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "analysis": "LCR is 118% [Source: ALCO_Tracker.xlsx, Liquidity tab]",
                "proposed_change": {
                    "value": "1.18",
                    "cell": "D10",
                    "tab": "Liquidity",
                    "reasoning": "LCR updated per Q1 report",
                },
                "confidence": 0.91,
                "escalation_flags": [],
            }
        )
    )
    return llm


REQUIRED_KEYS = {
    "agent_response", "agent_name", "proposed_value",
    "proposed_cell", "confidence_score",
}


def test_base_agent_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        BaseAgent(MagicMock(), MagicMock())  # type: ignore[abstract]


def test_liquidity_agent_name(mock_llm: LLMClient, mock_skills: SkillsLoader) -> None:
    assert LiquidityAgent(mock_llm, mock_skills).name == "liquidity-agent"


def test_capital_agent_name(mock_llm: LLMClient, mock_skills: SkillsLoader) -> None:
    assert CapitalAgent(mock_llm, mock_skills).name == "capital-agent"


def test_alm_agent_name(mock_llm: LLMClient, mock_skills: SkillsLoader) -> None:
    assert AlmAgent(mock_llm, mock_skills).name == "alm-agent"


def test_funding_agent_name(mock_llm: LLMClient, mock_skills: SkillsLoader) -> None:
    assert FundingAgent(mock_llm, mock_skills).name == "funding-agent"


@pytest.mark.asyncio
async def test_agent_returns_valid_structure(
    mock_llm: LLMClient, mock_skills: SkillsLoader,
) -> None:
    agent = LiquidityAgent(mock_llm, mock_skills)
    result = await agent.analyze({"query": "test", "context_text": ""})
    assert REQUIRED_KEYS.issubset(result.keys())
    assert result["agent_name"] == "liquidity-agent"
    assert isinstance(result["confidence_score"], float)


@pytest.mark.asyncio
async def test_agent_with_proposal(
    mock_llm_with_proposal: LLMClient, mock_skills: SkillsLoader,
) -> None:
    agent = LiquidityAgent(mock_llm_with_proposal, mock_skills)
    result = await agent.analyze({"query": "What is the LCR?", "context_text": "LCR is 118%"})
    assert result["proposed_value"] == "1.18"
    assert result["proposed_cell"] == "D10"
    assert result["proposed_tab"] == "Liquidity"
    assert result["confidence_score"] == 0.91


@pytest.mark.asyncio
async def test_agent_handles_llm_failure(mock_skills: SkillsLoader) -> None:
    llm = MagicMock(spec=LLMClient)
    llm.chat = AsyncMock(side_effect=Exception("LLM timeout"))
    agent = LiquidityAgent(llm, mock_skills)
    result = await agent.analyze({"query": "test"})
    assert result["proposed_value"] is None
    assert result["confidence_score"] == 0.0
    assert "error" in result["agent_response"].lower()


@pytest.mark.asyncio
async def test_agent_handles_non_json_response(mock_skills: SkillsLoader) -> None:
    llm = MagicMock(spec=LLMClient)
    llm.chat = AsyncMock(return_value="This is plain text, not JSON.")
    agent = LiquidityAgent(llm, mock_skills)
    result = await agent.analyze({"query": "test"})
    assert result["agent_response"] == "This is plain text, not JSON."
    assert result["proposed_value"] is None
    assert result["confidence_score"] == 0.5


@pytest.mark.asyncio
async def test_agent_run_wraps_analyze(mock_llm: LLMClient, mock_skills: SkillsLoader) -> None:
    agent = LiquidityAgent(mock_llm, mock_skills)
    state = {"query": "test", "context_text": ""}
    result = await agent.run(state)
    assert REQUIRED_KEYS.issubset(result.keys())


@pytest.mark.asyncio
async def test_agent_loads_skills(mock_llm: LLMClient, mock_skills: SkillsLoader) -> None:
    agent = LiquidityAgent(mock_llm, mock_skills)
    await agent.analyze({"query": "test"})
    mock_skills.load_agent_skills.assert_called_once_with(
        "liquidity-agent", "cac/liquidity-analysis",
    )
