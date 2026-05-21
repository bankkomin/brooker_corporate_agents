"""Unit tests for services/cac-orchestrator/src/nodes/grounding_gate.py."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# _is_conversational
# ---------------------------------------------------------------------------

class TestIsConversational:
    def _fn(self, q: str) -> bool:
        from services.cac_orchestrator.src.nodes.grounding_gate import _is_conversational
        return _is_conversational(q)

    def test_greeting_hi_is_conversational(self) -> None:
        assert self._fn("hi") is True

    def test_greeting_hello_is_conversational(self) -> None:
        assert self._fn("Hello!") is True

    def test_greeting_good_morning_is_conversational(self) -> None:
        assert self._fn("good morning") is True

    def test_thanks_is_conversational(self) -> None:
        assert self._fn("thanks") is True

    def test_what_can_you_do_is_conversational(self) -> None:
        assert self._fn("what can you do") is True

    def test_capabilities_word_alone_is_conversational(self) -> None:
        assert self._fn("capabilities") is True

    def test_capability_query_what_is_your_task(self) -> None:
        """'what is your task' must pass _CAPABILITY_RE anywhere in the string."""
        assert self._fn("what is your task?") is True

    def test_capability_query_what_is_your_mandate(self) -> None:
        assert self._fn("Can you tell me what is your mandate?") is True

    def test_capability_query_what_are_your_responsibilities(self) -> None:
        assert self._fn("what are your responsibilities") is True

    def test_long_substantive_query_not_conversational(self) -> None:
        q = "What was the total risk-weighted asset figure for Q3 2025 reported by treasury?"
        assert self._fn(q) is False

    def test_substantive_question_about_lcr_not_conversational(self) -> None:
        assert self._fn("What is the current LCR ratio in the ALCO tracker?") is False

    def test_word_count_over_limit_not_conversational(self) -> None:
        # 13 words — over _CONVERSATIONAL_MAX_WORDS=12 and no capability match
        q = "hi can you please help me with understanding what the Basel rules say"
        assert self._fn(q) is False


# ---------------------------------------------------------------------------
# _has_grounded_source
# ---------------------------------------------------------------------------

class TestHasGroundedSource:
    def _fn(self, sources, min_relevance=0.5):
        from services.cac_orchestrator.src.nodes.grounding_gate import _has_grounded_source
        return _has_grounded_source(sources, min_relevance)

    def test_empty_sources_returns_false(self) -> None:
        assert self._fn([]) is False

    def test_source_at_threshold_passes(self) -> None:
        assert self._fn([{"relevance_score": 0.5}], min_relevance=0.5) is True

    def test_source_above_threshold_passes(self) -> None:
        assert self._fn([{"score": 0.9}], min_relevance=0.5) is True

    def test_source_below_threshold_fails(self) -> None:
        assert self._fn([{"relevance_score": 0.3}], min_relevance=0.5) is False

    def test_mixed_sources_passes_if_any_meets_threshold(self) -> None:
        sources = [{"relevance_score": 0.2}, {"relevance_score": 0.8}]
        assert self._fn(sources, min_relevance=0.5) is True

    def test_all_below_threshold_fails(self) -> None:
        sources = [{"relevance_score": 0.1}, {"score": 0.4}]
        assert self._fn(sources, min_relevance=0.5) is False

    def test_missing_score_keys_treated_as_zero(self) -> None:
        assert self._fn([{"text": "no score here"}], min_relevance=0.5) is False


# ---------------------------------------------------------------------------
# grounding_gate (async) — full state integration
# ---------------------------------------------------------------------------

class TestGroundingGate:
    @pytest.mark.asyncio
    async def test_conversational_returns_is_grounded_true(self) -> None:
        from services.cac_orchestrator.src.nodes.grounding_gate import grounding_gate
        result = await grounding_gate({"query": "hello", "sources": [], "attached_files_text": ""})
        assert result["is_grounded"] is True
        assert "answer" not in result

    @pytest.mark.asyncio
    async def test_grounded_source_returns_is_grounded_true(self) -> None:
        from services.cac_orchestrator.src.nodes.grounding_gate import grounding_gate
        state = {
            "query": "What is the current LCR ratio?",
            "sources": [{"relevance_score": 0.75}],
            "attached_files_text": "",
        }
        result = await grounding_gate(state)
        assert result["is_grounded"] is True

    @pytest.mark.asyncio
    async def test_attached_files_make_it_grounded(self) -> None:
        from services.cac_orchestrator.src.nodes.grounding_gate import grounding_gate
        state = {
            "query": "Summarise this document about policy.",
            "sources": [],
            "attached_files_text": "Some uploaded document content here.",
        }
        result = await grounding_gate(state)
        assert result["is_grounded"] is True

    @pytest.mark.asyncio
    async def test_no_sources_no_attachments_returns_is_grounded_false(self) -> None:
        from services.cac_orchestrator.src.nodes.grounding_gate import grounding_gate, _ABSTENTION_ANSWER
        state = {
            "query": "What are the latest RWA figures from the hidden report?",
            "sources": [],
            "attached_files_text": "",
        }
        result = await grounding_gate(state)
        assert result["is_grounded"] is False
        assert result["answer"] == _ABSTENTION_ANSWER
        assert result["confidence"] == "Low"

    @pytest.mark.asyncio
    async def test_abstention_clears_staging_proposal_fields(self) -> None:
        from services.cac_orchestrator.src.nodes.grounding_gate import grounding_gate
        state = {
            "query": "What are the hidden internal figures?",
            "sources": [],
            "attached_files_text": "",
            "proposed_value": "3.15",
            "staging_proposal_id": "chg_001",
        }
        result = await grounding_gate(state)
        assert result["proposed_value"] is None
        assert result["staging_proposal_id"] is None

    @pytest.mark.asyncio
    async def test_low_score_sources_below_threshold_abstains(self) -> None:
        from services.cac_orchestrator.src.nodes.grounding_gate import grounding_gate
        state = {
            "query": "Show me the confidential funding data.",
            "sources": [{"relevance_score": 0.1}, {"relevance_score": 0.2}],
            "attached_files_text": "",
        }
        result = await grounding_gate(state)
        assert result["is_grounded"] is False

    @pytest.mark.asyncio
    async def test_capability_query_bypasses_regardless_of_no_sources(self) -> None:
        from services.cac_orchestrator.src.nodes.grounding_gate import grounding_gate
        state = {
            "query": "what is your task?",
            "sources": [],
            "attached_files_text": "",
        }
        result = await grounding_gate(state)
        assert result["is_grounded"] is True
