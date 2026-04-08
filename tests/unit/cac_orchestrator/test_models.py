"""Tests for cac-orchestrator Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from services.cac_orchestrator.src.models import (
    ManifestProposal,
    QueryRequest,
    QueryResponse,
    Source,
)


class TestSource:
    def test_valid_source(self, source_data: dict) -> None:
        source = Source(**source_data)
        assert source.type == "document"
        assert source.filename == "alco_tracker_2025.xlsx"
        assert source.page == 3
        assert source.date == "2025-11-01"
        assert source.uploader == "john.doe"
        assert source.relevance_score == 0.92

    def test_source_optional_fields_default_none(self) -> None:
        source = Source(
            type="knowledge",
            filename="internal_policy.pdf",
            excerpt="Risk appetite statement...",
            relevance_score=0.88,
        )
        assert source.page is None
        assert source.date is None
        assert source.uploader is None

    def test_source_chat_type(self) -> None:
        source = Source(
            type="chat",
            filename="#alco-channel",
            date="2025-10-15",
            excerpt="The team discussed the updated LCR threshold.",
            relevance_score=0.75,
        )
        assert source.type == "chat"

    def test_source_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            Source(  # type: ignore[call-arg]
                type="document",
                filename="doc.pdf",
                # excerpt and relevance_score missing
            )


class TestQueryRequest:
    def test_valid_request_all_fields(self, query_request_data: dict) -> None:
        req = QueryRequest(**query_request_data)
        assert req.query == "What was the LCR ratio last quarter?"
        assert req.user_id == "U12345678"
        assert req.channel == "C-alco-queries"
        assert req.thread_ts == "1711900000.000100"

    def test_request_thread_ts_optional(self) -> None:
        req = QueryRequest(
            query="What is the current NIM?",
            user_id="U99999",
            channel="C-finance",
        )
        assert req.thread_ts is None

    def test_request_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            QueryRequest(  # type: ignore[call-arg]
                query="Some query",
                # user_id and channel missing
            )


class TestQueryResponse:
    def test_valid_response_serialization(self, source_data: dict) -> None:
        source = Source(**source_data)
        resp = QueryResponse(
            answer="The LCR ratio was 1.12 in Q3 2025.",
            sources=[source],
            excel_nav="Liquidity!B12",
            staging_proposal_id="chg_0001",
            escalation_triggered=False,
            confidence="High",
            processing_time_ms=342,
        )
        data = resp.model_dump()
        assert data["answer"] == "The LCR ratio was 1.12 in Q3 2025."
        assert data["confidence"] == "High"
        assert data["processing_time_ms"] == 342
        assert len(data["sources"]) == 1
        assert data["escalation_triggered"] is False

    def test_response_optional_fields_default(self, source_data: dict) -> None:
        source = Source(**source_data)
        resp = QueryResponse(
            answer="No data found.",
            sources=[source],
            confidence="Low",
            processing_time_ms=120,
        )
        assert resp.excel_nav is None
        assert resp.staging_proposal_id is None
        assert resp.escalation_triggered is False


class TestManifestProposal:
    def test_valid_proposal_serialization(self, manifest_proposal_data: dict) -> None:
        proposal = ManifestProposal(**manifest_proposal_data)
        assert proposal.id == "chg_0001"
        assert proposal.agent == "alco_agent"
        assert proposal.triggered_by == "slack_query"
        assert proposal.slack_user == "U12345678"
        assert proposal.file == "alco_tracker.xlsx"
        assert proposal.tab == "Liquidity"
        assert proposal.cell == "B12"
        assert proposal.old_value == "1.05"
        assert proposal.new_value == "1.12"
        assert proposal.source == "alco_tracker_2025.xlsx"
        assert proposal.confidence == 0.91
        assert proposal.status == "pending"
        assert proposal.paperclip_ticket_id is None

    def test_proposal_default_status_is_pending(self, manifest_proposal_data: dict) -> None:
        data = {k: v for k, v in manifest_proposal_data.items() if k != "status"}
        proposal = ManifestProposal(**data)
        assert proposal.status == "pending"

    def test_proposal_all_prd_schema_fields_present(self) -> None:
        """All PRD-specified fields must exist on ManifestProposal."""
        expected_fields = {
            "id",
            "created_at",
            "agent",
            "triggered_by",
            "slack_user",
            "file",
            "tab",
            "cell",
            "old_value",
            "new_value",
            "source",
            "source_excerpt",
            "confidence",
            "reasoning",
            "status",
            "paperclip_ticket_id",
        }
        actual_fields = set(ManifestProposal.model_fields.keys())
        assert expected_fields == actual_fields

    def test_proposal_old_value_optional(self, manifest_proposal_data: dict) -> None:
        data = dict(manifest_proposal_data)
        data.pop("old_value")
        proposal = ManifestProposal(**data)
        assert proposal.old_value is None

    def test_proposal_model_dump_matches_schema(self, manifest_proposal_data: dict) -> None:
        proposal = ManifestProposal(**manifest_proposal_data)
        dumped = proposal.model_dump()
        for field in manifest_proposal_data:
            assert field in dumped
