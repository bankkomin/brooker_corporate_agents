"""Tests for B4 synthesis_proposer — mocks Qdrant + embedder + LLM."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.rag_ingestion.src.synthesis_proposer import (
    _build_frontmatter,
    _passages_for_entity,
    _render_passages,
    _source_files_from,
    propose_for_candidate,
    scan_and_propose,
)
from services.rag_ingestion.src.synthesis_tracker import SynthesisCandidate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hits(*items):
    """Return a list of hit dicts from (source, text, score) tuples."""
    return [
        {"source_file": s, "text": t, "score": sc}
        for s, t, sc in items
    ]


def test_render_passages_truncates_long_text():
    hits = _hits(("doc.pdf", "x" * 600, 0.9))
    rendered = _render_passages(hits)
    assert "[1] (from doc.pdf)" in rendered
    assert len(rendered) < 800  # truncated to 500 + a bit of framing


def test_render_passages_empty_returns_placeholder():
    assert "(no passages retrieved" in _render_passages([])


def test_source_files_dedup_preserves_order():
    hits = _hits(
        ("a.pdf", "...", 0.9),
        ("b.pdf", "...", 0.8),
        ("a.pdf", "...", 0.7),  # dup
    )
    assert _source_files_from(hits) == ["a.pdf", "b.pdf"]


def test_build_frontmatter_has_required_fields():
    fm = _build_frontmatter(
        entity_slug="audit-committee",
        entity_display="Audit Committee",
        dept="regulations",
        sources=["SEC_Code.pdf"],
        today=date(2026, 5, 26),
    )
    assert "type: \"concept\"" in fm
    assert "department: \"regulations\"" in fm
    assert "auto-synthesized" in fm
    assert "SEC_Code.pdf" in fm


# ---------------------------------------------------------------------------
# _passages_for_entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passages_for_entity_collects_from_both_collections():
    embedder = AsyncMock()
    embedder.embed_texts.return_value = [[0.1] * 4]
    store = AsyncMock()

    async def fake_search(*, collection, **kwargs):
        if collection.endswith("_docs"):
            return _hits(("doc1.pdf", "doc text", 0.9))
        return _hits(("note.md", "knowledge note", 0.85))

    store.search = fake_search
    hits = await _passages_for_entity(
        entity_display="Audit Committee", dept="regulations",
        embedder=embedder, store=store,
    )
    sources = {h["source_file"] for h in hits}
    assert "doc1.pdf" in sources
    assert "note.md" in sources


@pytest.mark.asyncio
async def test_passages_for_entity_handles_collection_failure():
    embedder = AsyncMock()
    embedder.embed_texts.return_value = [[0.1] * 4]
    store = AsyncMock()

    async def fake_search(*, collection, **kwargs):
        if collection.endswith("_docs"):
            raise RuntimeError("docs collection unavailable")
        return _hits(("note.md", "ok", 0.85))

    store.search = fake_search
    hits = await _passages_for_entity(
        entity_display="X", dept="cac", embedder=embedder, store=store,
    )
    # Should still return the one collection that worked
    assert len(hits) == 1
    assert hits[0]["source_file"] == "note.md"


# ---------------------------------------------------------------------------
# propose_for_candidate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_for_candidate_writes_manifest_and_marks_proposed(tmp_path: Path):
    embedder = AsyncMock()
    embedder.embed_texts.return_value = [[0.1] * 4]
    store = AsyncMock()
    store.search.return_value = _hits(
        ("SEC_Code.pdf", "Audit committee must consist of at least 3 members.", 0.9),
        ("Audit_Charter.docx", "The committee reviews internal controls quarterly.", 0.88),
    )

    pool = MagicMock()
    conn = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=cm)

    async def fake_llm(prompt: str) -> str:
        assert "Audit Committee" in prompt
        assert "SEC_Code.pdf" in prompt
        return "# Audit Committee\n\n## TL;DR for Agents\n**Retrieved by:** x\n**Answers:** \"q\"\n**Key facts:** facts\n\n## Summary\n\nAuto draft.\n"

    candidate = SynthesisCandidate(
        entity="audit-committee", dept="regulations",
        source_count=4, threshold_used=2,
    )
    pid = await propose_for_candidate(
        candidate, pool=pool, embedder=embedder, store=store,
        staging_path=str(tmp_path), llm=fake_llm,
        entity_display_lookup={"audit-committee": "Audit Committee"},
        today=date(2026, 5, 26),
    )
    assert pid is not None
    manifest_path = tmp_path / "pending" / pid / "manifest.json"
    assert manifest_path.is_file()
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert m["target_vault_path"] == "regulations/concepts/audit-committee.md"
    assert m["operation"] == "create"
    assert m["agent"] == "synthesis-proposer"
    assert m["synthesis_evidence"]["source_count"] == 4
    assert m["synthesis_evidence"]["threshold_used"] == 2
    assert "SEC_Code.pdf" in m["synthesis_evidence"]["sources"]

    # mark_proposed should have INSERTed into synthesis_state
    conn.execute.assert_called()
    sql_call = conn.execute.call_args
    assert "synthesis_state" in sql_call[0][0]


@pytest.mark.asyncio
async def test_propose_for_candidate_returns_none_on_empty_llm(tmp_path: Path):
    embedder = AsyncMock()
    embedder.embed_texts.return_value = [[0.1] * 4]
    store = AsyncMock()
    store.search.return_value = _hits(("x.pdf", "...", 0.9))
    pool = MagicMock()

    async def empty_llm(prompt: str) -> str:
        return ""

    pid = await propose_for_candidate(
        SynthesisCandidate(entity="x", dept="cac", source_count=3, threshold_used=3),
        pool=pool, embedder=embedder, store=store,
        staging_path=str(tmp_path), llm=empty_llm,
    )
    assert pid is None
    assert not (tmp_path / "pending").exists()


@pytest.mark.asyncio
async def test_propose_for_candidate_swallows_llm_exception(tmp_path: Path):
    embedder = AsyncMock()
    embedder.embed_texts.return_value = [[0.1] * 4]
    store = AsyncMock()
    store.search.return_value = _hits(("x.pdf", "...", 0.9))
    pool = MagicMock()

    async def bad_llm(prompt: str) -> str:
        raise RuntimeError("LLM down")

    pid = await propose_for_candidate(
        SynthesisCandidate(entity="x", dept="cac", source_count=3, threshold_used=3),
        pool=pool, embedder=embedder, store=store,
        staging_path=str(tmp_path), llm=bad_llm,
    )
    assert pid is None


# ---------------------------------------------------------------------------
# scan_and_propose
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_and_propose_aggregates(tmp_path: Path, monkeypatch):
    candidates = [
        SynthesisCandidate(entity="a", dept="regulations", source_count=4, threshold_used=2),
        SynthesisCandidate(entity="b", dept="cac", source_count=5, threshold_used=3),
    ]
    async def fake_find(*args, **kwargs):
        return candidates

    # Patch on the module object directly — the hyphen-mapped import path
    # (services.rag_ingestion.src.synthesis_proposer) can't be resolved by
    # monkeypatch.setattr's dotted-string lookup, so we resolve the module
    # ourselves and patch the attribute.
    from services.rag_ingestion.src import synthesis_proposer as sp_mod
    monkeypatch.setattr(sp_mod, "find_synthesis_candidates", fake_find)
    monkeypatch.setattr(sp_mod, "load_thresholds", lambda p: {"default": 3, "per_dept": {}})

    embedder = AsyncMock()
    embedder.embed_texts.return_value = [[0.1] * 4]
    store = AsyncMock()
    store.search.return_value = _hits(("x.pdf", "...", 0.9))
    pool = MagicMock()
    conn = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=cm)

    async def llm(p):
        return "# Title\n\nbody"

    result = await scan_and_propose(
        pool=pool, embedder=embedder, store=store,
        staging_path=str(tmp_path), llm=llm,
        thresholds_path="ignored",
        today=date(2026, 5, 26),
    )
    assert result["candidates"] == 2
    assert result["proposed"] == 2
    assert len(result["proposal_ids"]) == 2
