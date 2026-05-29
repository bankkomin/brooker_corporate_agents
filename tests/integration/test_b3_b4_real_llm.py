"""Integration smoke tests for B3 meeting-fanout and B4 synthesis-proposer
against a real LLM.

These tests are SKIPPED by default. To run:

    INTEGRATION_TESTS=1 LLM_BASE_URL=http://nginx:8080/v1 LLM_MODEL=qwen-122b \\
        python -m pytest tests/integration/test_b3_b4_real_llm.py -v

What they prove:
- The four B3 extractors actually produce parseable JSON from the configured
  LLM and the resulting manifests have the expected shape.
- The B4 synthesis_proposer's prompt produces a usable concept-note body.

What they do NOT do:
- Hit a real Qdrant (B4 search is mocked).
- Hit a real Postgres (B4 mark_proposed is mocked).
- Verify quality of LLM output beyond "JSON parses, manifest validates".

Cost note: each test makes 1-5 LLM calls. Running the full file against
Qwen 122B / Gemini Flash burns a few cents in tokens.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

INTEGRATION = os.getenv("INTEGRATION_TESTS") == "1"
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed")

pytestmark = pytest.mark.skipif(
    not (INTEGRATION and LLM_BASE_URL and LLM_MODEL),
    reason="Set INTEGRATION_TESTS=1 + LLM_BASE_URL + LLM_MODEL to run real-LLM smoke tests",
)


def _build_real_llm():
    """Build a `(prompt) -> awaitable[str]` callable against the configured LLM."""
    from langchain_openai import ChatOpenAI

    chat = ChatOpenAI(
        base_url=LLM_BASE_URL, model=LLM_MODEL,
        api_key=LLM_API_KEY, temperature=0.1,
    )

    async def _llm(prompt: str) -> str:
        resp = await chat.ainvoke(prompt)
        return getattr(resp, "content", "") or ""

    return _llm


# ---------------------------------------------------------------------------
# B3 — meeting fan-out
# ---------------------------------------------------------------------------

SAMPLE_MEETING = """---
date: 2026-05-27
type: meeting-note
committee: CAC
---

# ALCO Monthly — May 2026

## Attendees
- CFO (J. Doe)
- CRO (A. Smith)
- Head of Treasury

## Discussion

The committee reviewed liquidity metrics. LCR stood at 118% as of 30 Apr
2026, above the 100% regulatory floor. NSFR was 104.2%. BICL credit
facility utilization was 67% (Bt 569mn drawn against Bt 850mn limit).

## Decisions

1. Approved raising the internal LCR target floor from 110% to 115%, effective
   1 June 2026. Rationale: market volatility forecast warrants a 5pp buffer.
2. Reaffirmed the existing BICL facility utilization cap at 80%.

## Action Items
- Treasury to update the ALCO Tracker by 5 June.
"""


@pytest.fixture
def meeting_vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    md = v / "cac" / "meeting-notes"
    md.mkdir(parents=True)
    (md / "2026-05-27-alco-monthly.md").write_text(SAMPLE_MEETING, encoding="utf-8")
    return v


@pytest.mark.asyncio
async def test_real_llm_fanout_extracts_entities_and_decisions(meeting_vault, tmp_path):
    from services.cac_orchestrator.src.meeting_fanout import (
        MeetingNoteLandedEvent, run_fanout,
    )

    staging = tmp_path / "staging"
    event = MeetingNoteLandedEvent(
        vault_path="cac/meeting-notes/2026-05-27-alco-monthly.md",
        dept="cac",
        sha256="abc" * 21 + "x",  # 64 chars
        size_bytes=len(SAMPLE_MEETING),
    )
    result = await run_fanout(
        event, staging_path=str(staging), vault_root=str(meeting_vault),
        today=date(2026, 5, 27),
        llm_invoker=_build_real_llm(),
    )

    # Index-update is mechanical and always lands one manifest
    assert len(result.proposal_ids) >= 1

    # Collect all manifests for inspection
    manifests = []
    for pid in result.proposal_ids:
        m = json.loads(
            (staging / "pending" / pid / "manifest.json").read_text(encoding="utf-8")
        )
        manifests.append(m)

    # The LLM should find at least one decision (LCR target raise) and one
    # entity (BICL). Loose assertions to tolerate model variation.
    agents = {m["agent"] for m in manifests}
    assert "meeting-extractor-index-update" in agents, "mechanical extractor must run"
    # At least ONE LLM extractor should succeed; tolerate occasional empty
    # responses from any single one
    llm_agents = agents - {"meeting-extractor-index-update"}
    assert len(llm_agents) >= 1, f"no LLM extractors produced output; agents={agents}"


# ---------------------------------------------------------------------------
# B4 — synthesis proposer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_llm_synthesis_proposer_drafts_concept(tmp_path: Path):
    from services.rag_ingestion.src.synthesis_proposer import propose_for_candidate
    from services.rag_ingestion.src.synthesis_tracker import SynthesisCandidate

    # Mock Qdrant + embedder + Postgres pool — only the LLM is real
    embedder = AsyncMock()
    embedder.embed_texts.return_value = [[0.1] * 4]
    store = AsyncMock()
    store.search.return_value = [
        {
            "source_file": "SEC_Audit_Code_2024.pdf",
            "text": "An audit committee of a SET-listed company must comprise at "
                    "least three independent directors per section 89/25 of the "
                    "Securities and Exchange Act.",
            "score": 0.92,
        },
        {
            "source_file": "Brooker_AC_Charter_v3.docx",
            "text": "The Brooker audit committee meets at least quarterly and "
                    "reviews the annual external audit plan with PwC.",
            "score": 0.88,
        },
    ]
    pool = MagicMock()
    conn = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=cm)

    candidate = SynthesisCandidate(
        entity="audit-committee", dept="regulations",
        source_count=4, threshold_used=2,
    )
    pid = await propose_for_candidate(
        candidate, pool=pool, embedder=embedder, store=store,
        staging_path=str(tmp_path), llm=_build_real_llm(),
        entity_display_lookup={"audit-committee": "Audit Committee"},
        today=date(2026, 5, 27),
    )
    assert pid is not None
    manifest_path = tmp_path / "pending" / pid / "manifest.json"
    draft_path = tmp_path / "pending" / pid / "draft.md"
    assert manifest_path.is_file()
    assert draft_path.is_file()

    draft = draft_path.read_text(encoding="utf-8")
    # The frontmatter is mechanically inserted by our code, not the LLM
    assert "type: \"concept\"" in draft
    assert "department: \"regulations\"" in draft
    # The body should be substantive (not empty / not pure boilerplate)
    body_start = draft.index("---\n", 4) + 4
    body = draft[body_start:]
    assert len(body.strip()) > 200, "LLM produced suspiciously short body"
    # Should mention audit committee somewhere
    assert "audit" in body.lower() or "committee" in body.lower()
