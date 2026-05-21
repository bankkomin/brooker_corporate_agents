"""Unit tests for slack-bot channel routing, QueryRequest dept_id, and intent fast-paths."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Stub heavy deps not in the unit-test venv so the slack-bot modules import.
# Must run before any service import.
# ---------------------------------------------------------------------------

def _stub_slack_deps() -> None:
    """Inject minimal stubs for slack_bolt and local sibling modules."""
    if "slack_bolt" not in sys.modules:
        bolt = types.ModuleType("slack_bolt")
        async_app_mod = types.ModuleType("slack_bolt.async_app")

        class _AsyncApp:
            def __init__(self, *a, **kw): pass
            def event(self, *a, **kw):
                def decorator(fn): return fn
                return decorator

        async_app_mod.AsyncApp = _AsyncApp
        bolt.async_app = async_app_mod
        sys.modules["slack_bolt"] = bolt
        sys.modules["slack_bolt.async_app"] = async_app_mod

    # Stub out the sibling modules that events.py imports.
    _svc = Path(__file__).resolve().parents[4] / "services" / "slack-bot" / "src"
    pkg = "services.slack_bot.src"
    for sub in ("clients", "file_handler", "responder"):
        mod_name = f"{pkg}.{sub}"
        if mod_name not in sys.modules:
            m = types.ModuleType(mod_name)
            if sub == "clients":
                m.OrchestratorClient = MagicMock  # type: ignore[attr-defined]
                m.RAGIngestionClient = MagicMock  # type: ignore[attr-defined]
            elif sub == "file_handler":
                m.download_and_forward_file = AsyncMock()  # type: ignore[attr-defined]
            elif sub == "responder":
                m.post_error_to_thread = AsyncMock()  # type: ignore[attr-defined]
                m.reply_in_thread = AsyncMock()  # type: ignore[attr-defined]
            sys.modules[mod_name] = m


_stub_slack_deps()


# ---------------------------------------------------------------------------
# _dept_from_channel_name
# ---------------------------------------------------------------------------

class TestDeptFromChannelName:
    def _fn(self, name: str):
        from services.slack_bot.src.events import _dept_from_channel_name
        return _dept_from_channel_name(name)

    def test_risk_committee_maps_to_risk(self) -> None:
        assert self._fn("risk-committee") == "risk"

    def test_hr_head_maps_to_hr(self) -> None:
        assert self._fn("hr-head") == "hr"

    def test_agent_escalations_returns_none(self) -> None:
        assert self._fn("agent-escalations") is None

    def test_all_brook_corporate_ai_agents_returns_none(self) -> None:
        assert self._fn("all-brook-corporate-ai-agents") is None

    def test_cac_committee_maps_to_cac(self) -> None:
        assert self._fn("cac-committee") == "cac"

    def test_finance_channel_maps_to_finance(self) -> None:
        assert self._fn("finance-updates") == "finance"

    def test_legal_desk_maps_to_legal(self) -> None:
        assert self._fn("legal-desk") == "legal"

    def test_it_support_maps_to_it(self) -> None:
        assert self._fn("it-support") == "it"

    def test_underscore_separator_normalised(self) -> None:
        """Underscores in channel names treated like hyphens."""
        assert self._fn("hr_head") == "hr"

    def test_general_channel_no_dept_token_returns_none(self) -> None:
        assert self._fn("general") is None

    def test_ceo_channel_maps_to_ceo(self) -> None:
        assert self._fn("ceo-updates") == "ceo"

    def test_empty_name_returns_none(self) -> None:
        assert self._fn("") is None


# ---------------------------------------------------------------------------
# QueryRequest — dept_id regression (was causing 400 bug)
# ---------------------------------------------------------------------------

class TestQueryRequestDeptId:
    def test_dept_id_present_in_model_dump(self) -> None:
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(
            query="What is the LCR?",
            channel="C-risk-123",
            user_id="U999",
            dept_id="risk",
        )
        dumped = q.model_dump()
        assert "dept_id" in dumped
        assert dumped["dept_id"] == "risk"

    def test_dept_id_defaults_to_none(self) -> None:
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(query="hello", channel="C-123", user_id="U1")
        assert q.dept_id is None
        assert q.model_dump()["dept_id"] is None

    def test_dept_id_round_trips_through_model(self) -> None:
        """Passing dept_id as kwarg is preserved — regression for the 400 bug."""
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(
            query="Show me the NSFR",
            channel="C-cac",
            user_id="U123",
            thread_ts="1234567.000",
            dept_id="cac",
        )
        assert q.dept_id == "cac"
        assert q.model_dump()["dept_id"] == "cac"

    def test_query_request_uses_channel_field_not_channel_id(self) -> None:
        """Confirm the field is 'channel', not 'channel_id'."""
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(query="test", channel="C123", user_id="U1")
        assert q.channel == "C123"


# ---------------------------------------------------------------------------
# IntentRouter — regex fast-path tests (no LLM HTTP call made)
# ---------------------------------------------------------------------------

class TestIntentRouterRegexFastPaths:
    """The three regex short-circuits in IntentRouter.classify() are exercised
    here without any real HTTP call.  httpx.AsyncClient.post is never reached.
    """

    @pytest.fixture
    def router(self):
        from services.slack_bot.src.intent_router import IntentRouter
        return IntentRouter(
            llm_url="http://localhost:9999/v1",
            llm_model="test-model",
            timeout=1.0,
        )

    @pytest.mark.asyncio
    async def test_deck_verb_create_returns_deck(self, router) -> None:
        intent = await router.classify("create a pitch deck about our Q3 results")
        assert intent.name == "deck"
        assert intent.confidence == pytest.approx(0.95)
        assert "deck_verb" in intent.reason

    @pytest.mark.asyncio
    async def test_deck_verb_generate_slides_returns_deck(self, router) -> None:
        intent = await router.classify("generate slides on the funding strategy")
        assert intent.name == "deck"

    @pytest.mark.asyncio
    async def test_deck_verb_draft_presentation_returns_deck(self, router) -> None:
        intent = await router.classify("draft a presentation for the board")
        assert intent.name == "deck"

    @pytest.mark.asyncio
    async def test_deck_noun_lead_deck_about_returns_deck(self, router) -> None:
        intent = await router.classify("deck about the Q2 fundraising round")
        assert intent.name == "deck"
        assert intent.confidence == pytest.approx(0.95)
        assert "deck_noun_lead" in intent.reason

    @pytest.mark.asyncio
    async def test_deck_noun_lead_slides_on_returns_deck(self, router) -> None:
        intent = await router.classify("slides on the Basel III capital requirements")
        assert intent.name == "deck"

    @pytest.mark.asyncio
    async def test_deck_noun_lead_presentation_for_returns_deck(self, router) -> None:
        intent = await router.classify("presentation for the investor meeting")
        assert intent.name == "deck"

    @pytest.mark.asyncio
    async def test_chat_short_circuit_hi_returns_chat(self, router) -> None:
        intent = await router.classify("hi")
        assert intent.name == "chat"
        assert "question" in intent.reason

    @pytest.mark.asyncio
    async def test_chat_short_circuit_hello_returns_chat(self, router) -> None:
        intent = await router.classify("hello!")
        assert intent.name == "chat"

    @pytest.mark.asyncio
    async def test_chat_short_circuit_what_is_returns_chat(self, router) -> None:
        intent = await router.classify("what is the LCR ratio?")
        assert intent.name == "chat"

    @pytest.mark.asyncio
    async def test_chat_short_circuit_tell_me_about_returns_chat(self, router) -> None:
        intent = await router.classify("tell me about the ALCO committee")
        assert intent.name == "chat"

    @pytest.mark.asyncio
    async def test_chat_short_circuit_how_returns_chat(self, router) -> None:
        intent = await router.classify("how does Basel III capital work?")
        assert intent.name == "chat"

    @pytest.mark.asyncio
    async def test_empty_string_returns_chat_confidence_1(self, router) -> None:
        intent = await router.classify("")
        assert intent.name == "chat"
        assert intent.confidence == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_question_about_deck_returns_chat_not_deck(self, router) -> None:
        """'what is a pitch deck' asks about decks but is not a generation request."""
        intent = await router.classify("what is a pitch deck?")
        assert intent.name == "chat"
