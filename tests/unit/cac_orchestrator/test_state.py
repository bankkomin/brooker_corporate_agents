"""Tests for AgentState TypedDict definition."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _stub_langgraph_and_langchain() -> None:
    """Stub langgraph and langchain_core so state.py can be imported without them installed."""
    # langchain_core.messages
    lc_messages = types.ModuleType("langchain_core.messages")
    lc_messages.BaseMessage = MagicMock  # type: ignore[attr-defined]
    lc_core = types.ModuleType("langchain_core")
    lc_core.messages = lc_messages  # type: ignore[attr-defined]
    sys.modules.setdefault("langchain_core", lc_core)
    sys.modules.setdefault("langchain_core.messages", lc_messages)

    # langgraph.graph.message
    lg_graph_msg = types.ModuleType("langgraph.graph.message")
    lg_graph_msg.add_messages = lambda x: x  # type: ignore[attr-defined]
    lg_graph = types.ModuleType("langgraph.graph")
    lg_graph.message = lg_graph_msg  # type: ignore[attr-defined]
    lg = types.ModuleType("langgraph")
    lg.graph = lg_graph  # type: ignore[attr-defined]
    sys.modules.setdefault("langgraph", lg)
    sys.modules.setdefault("langgraph.graph", lg_graph)
    sys.modules.setdefault("langgraph.graph.message", lg_graph_msg)


# Stub before any import of state.py
_stub_langgraph_and_langchain()

from services.cac_orchestrator.src.state import AgentState  # noqa: E402


class TestAgentStateDefinition:
    def test_agent_state_is_typeddict(self) -> None:
        """AgentState must be a TypedDict (has __annotations__ and __total__)."""
        assert hasattr(AgentState, "__annotations__")
        assert hasattr(AgentState, "__total__")

    def test_agent_state_can_be_used_as_dict(self) -> None:
        """TypedDict is compatible with plain dict construction."""
        state: AgentState = {  # type: ignore[typeddict-item]
            "query": "test query",
            "user_id": "U123",
            "channel": "C-test",
            "thread_ts": None,
            "messages": [],
            "intent": "qa",
            "intent_confidence": 0.95,
            "sources": [],
            "context_text": "",
            "agent_response": "",
            "agent_name": "alco_agent",
            "proposed_value": None,
            "proposed_cell": None,
            "escalation_triggered": False,
            "escalation_detail": None,
            "excel_nav": None,
            "validation_passed": True,
            "validation_warnings": [],
            "staging_proposal_id": None,
            "answer": "",
            "confidence": "High",
            "confidence_score": 0.95,
            "processing_start": 1711900000.0,
            "paperclip_ticket_id": None,
        }
        assert state["query"] == "test query"
        assert state["user_id"] == "U123"

    def test_all_expected_keys_present(self) -> None:
        """All required state keys must be declared in AgentState.__annotations__."""
        expected_keys = {
            # Input
            "query",
            "user_id",
            "channel",
            "thread_ts",
            "messages",
            # Intent classification
            "intent",
            "intent_confidence",
            # Context retrieval
            "sources",
            "context_text",
            # Agent output
            "agent_response",
            "agent_name",
            "proposed_value",
            "proposed_cell",
            # Escalation
            "escalation_triggered",
            "escalation_detail",
            # Excel navigation
            "excel_nav",
            # Validation
            "validation_passed",
            "validation_warnings",
            # Staging
            "staging_proposal_id",
            # Synthesis
            "answer",
            "confidence",
            "confidence_score",
            # Metadata
            "processing_start",
            "paperclip_ticket_id",
        }
        actual_keys = set(AgentState.__annotations__.keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing keys in AgentState: {missing}"

    def test_messages_field_has_annotated_type(self) -> None:
        """messages annotation string must reference Annotated for LangGraph."""
        # With `from __future__ import annotations`, all annotations are strings.
        # We inspect the raw string to verify the intended annotation shape.
        raw = AgentState.__annotations__["messages"]
        annotation_str = str(raw)
        assert "Annotated" in annotation_str, (
            f"messages field must be Annotated[...] but annotation is: {annotation_str}"
        )

    def test_optional_fields_annotated_correctly(self) -> None:
        """Fields that can be None must reference None in their annotation string."""
        # With `from __future__ import annotations`, annotations are ForwardRef strings.
        # Verify each nullable field's annotation string contains 'None'.
        annotations = AgentState.__annotations__

        nullable_fields = [
            "thread_ts",
            "proposed_value",
            "proposed_cell",
            "escalation_detail",
            "excel_nav",
            "staging_proposal_id",
            "paperclip_ticket_id",
        ]
        for field in nullable_fields:
            annotation = annotations[field]
            annotation_str = str(annotation)
            assert "None" in annotation_str, (
                f"Field '{field}' should allow None but annotation is: {annotation_str}"
            )
