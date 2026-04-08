"""Shared fixtures for cac-orchestrator unit tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def source_data() -> dict:
    return {
        "type": "document",
        "filename": "alco_tracker_2025.xlsx",
        "page": 3,
        "date": "2025-11-01",
        "uploader": "john.doe",
        "excerpt": "The ALCO committee reviewed liquidity metrics...",
        "relevance_score": 0.92,
    }


@pytest.fixture
def query_request_data() -> dict:
    return {
        "query": "What was the LCR ratio last quarter?",
        "user_id": "U12345678",
        "channel": "C-alco-queries",
        "thread_ts": "1711900000.000100",
    }


@pytest.fixture
def manifest_proposal_data() -> dict:
    return {
        "id": "chg_0001",
        "created_at": "2025-11-01T10:30:00Z",
        "agent": "alco_agent",
        "triggered_by": "slack_query",
        "slack_user": "U12345678",
        "file": "alco_tracker.xlsx",
        "tab": "Liquidity",
        "cell": "B12",
        "old_value": "1.05",
        "new_value": "1.12",
        "source": "alco_tracker_2025.xlsx",
        "source_excerpt": "LCR ratio as of Q3 2025 is 1.12",
        "confidence": 0.91,
        "reasoning": "Source document explicitly states the updated LCR ratio.",
        "status": "pending",
        "paperclip_ticket_id": None,
    }
