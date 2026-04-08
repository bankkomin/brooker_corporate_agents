"""Tests for the decision article generator."""
from __future__ import annotations

import textwrap
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.wiki_compiler.src.generators.decision import generate
from services.wiki_compiler.src.models import CompileEvent, WikiArticle

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CANNED_RESPONSE = textwrap.dedent("""\
    ---
    title: Decision — Funding Facilities E8 Update
    type: decision
    department: cac
    sources:
    - Slack #cac-committee | Jane Doe | 2026-04-07T10:42
    related: []
    created: '2026-04-07'
    updated: '2026-04-07'
    confidence: high
    coverage: medium
    tags:
    - funding
    ticket_id: null
    ---

    ## Summary

    The drawn balance for the BBK Revolving Credit Facility was updated from 72 to 78.

    ## Change Details

    Cell E8 in the Funding Facilities tab was changed from 72 to 78.

    ## Rationale

    Updated based on latest facility draw notification.

    ## Source Evidence

    Slack message from Jane Doe on 2026-04-07.

    ## Impact

    Increases total drawn balance by 6M THB.
""")

DECISION_PAYLOAD = {
    "proposal_id": "chg_0042",
    "agent": "funding-agent",
    "file": "ALCO_Tracker.xlsx",
    "tab": "Funding Facilities",
    "cell": "E8",
    "old_value": "72",
    "new_value": "78",
    "source": "Slack #cac-committee | Jane Doe | 2026-04-07T10:42",
    "confidence": 0.91,
    "reasoning": "Updated based on latest facility draw notification",
    "reviewer": "john.doe@brooker.co.th",
}


@pytest.fixture
def compiler_mock() -> MagicMock:
    mock = MagicMock()
    mock._call_llm = AsyncMock(return_value=CANNED_RESPONSE)
    return mock


@pytest.fixture
def decision_event() -> CompileEvent:
    return CompileEvent(
        event_type="proposal_approved",
        dept_id="cac",
        payload=DECISION_PAYLOAD,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_wiki_article(
    decision_event: CompileEvent,
    compiler_mock: MagicMock,
) -> None:
    """generate() returns a WikiArticle with type='decision'."""
    article = await generate(decision_event, compiler_mock)

    assert isinstance(article, WikiArticle)
    assert article.frontmatter.type == "decision"


@pytest.mark.asyncio
async def test_file_path_contains_date_and_slug(
    decision_event: CompileEvent,
    compiler_mock: MagicMock,
) -> None:
    """file_path follows the pattern {dept}/decisions/{date}-{slug}.md."""
    article = await generate(decision_event, compiler_mock)

    # Must be under the cac/decisions directory
    assert article.file_path.startswith("cac/decisions/")
    # Must contain a date segment (YYYY-MM-DD)
    import re

    assert re.search(r"\d{4}-\d{2}-\d{2}", article.file_path), (
        f"No date found in file_path: {article.file_path}"
    )
    # Must end with .md
    assert article.file_path.endswith(".md")


@pytest.mark.asyncio
async def test_frontmatter_department_and_confidence(
    decision_event: CompileEvent,
    compiler_mock: MagicMock,
) -> None:
    """Frontmatter carries the correct department and a valid confidence level."""
    article = await generate(decision_event, compiler_mock)

    assert article.frontmatter.department == "cac"
    # Payload confidence 0.91 should map to 'high'
    assert article.frontmatter.confidence == "high"
