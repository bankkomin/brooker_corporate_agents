"""Tests for the meeting-note article generator."""
from __future__ import annotations

import textwrap
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.wiki_compiler.src.generators.meeting import generate
from services.wiki_compiler.src.models import CompileEvent, WikiArticle

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CANNED_RESPONSE = textwrap.dedent("""\
    ---
    title: CAC Meeting Notes — 2026-04-07
    type: meeting-note
    department: cac
    sources:
    - Slack #cac-committee
    related: []
    created: '2026-04-07'
    updated: '2026-04-07'
    confidence: medium
    coverage: medium
    tags:
    - meeting
    - cac
    ticket_id: null
    ---

    ## Attendees

    - jane.doe
    - john.smith

    ## Topics Discussed

    - LCR at 115%
    - NSFR trend concerns

    ## Decisions Made

    No formal decisions recorded.

    ## Action Items

    - Monitor NSFR trend.

    ## Follow-Up

    Review at next weekly meeting.
""")

MEETING_PAYLOAD = {
    "channel": "#cac-committee",
    "date": "2026-04-07",
    "messages": [
        {
            "author": "jane.doe",
            "text": "LCR looks strong this month at 115%",
            "ts": "1712462520",
        },
        {
            "author": "john.smith",
            "text": "Agreed, but watch the NSFR trend",
            "ts": "1712462580",
        },
    ],
    "participants": ["jane.doe", "john.smith"],
    "thread_count": 15,
}


@pytest.fixture
def compiler_mock() -> MagicMock:
    mock = MagicMock()
    mock._call_llm = AsyncMock(return_value=CANNED_RESPONSE)
    return mock


@pytest.fixture
def meeting_event() -> CompileEvent:
    return CompileEvent(
        event_type="slack_digest",
        dept_id="cac",
        payload=MEETING_PAYLOAD,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_wiki_article(
    meeting_event: CompileEvent,
    compiler_mock: MagicMock,
) -> None:
    """generate() returns a WikiArticle with type='meeting-note'."""
    article = await generate(meeting_event, compiler_mock)

    assert isinstance(article, WikiArticle)
    assert article.frontmatter.type == "meeting-note"


@pytest.mark.asyncio
async def test_file_path_contains_date(
    meeting_event: CompileEvent,
    compiler_mock: MagicMock,
) -> None:
    """file_path lives under meeting-notes and contains the digest date."""
    article = await generate(meeting_event, compiler_mock)

    assert "meeting-notes" in article.file_path
    # The payload date (2026-04-07) should appear in the path
    assert "2026-04-07" in article.file_path
    assert article.file_path.endswith(".md")


@pytest.mark.asyncio
async def test_body_contains_attendee_info(
    meeting_event: CompileEvent,
    compiler_mock: MagicMock,
) -> None:
    """The article body (or frontmatter sources) includes participant names."""
    article = await generate(meeting_event, compiler_mock)

    # The LLM response lists attendees in the body; verify at least one name is present
    combined = article.body + str(article.frontmatter.sources)
    assert "jane.doe" in combined or "john.smith" in combined
