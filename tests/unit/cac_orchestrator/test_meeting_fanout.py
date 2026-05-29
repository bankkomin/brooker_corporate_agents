"""Tests for B3 meeting fan-out — LLM extractors with injected stub invokers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from services.cac_orchestrator.src.meeting_fanout import (
    EXTRACTORS,
    FanoutResult,
    MeetingNoteLandedEvent,
    _clamp_confidence,
    _safe_json,
    _safe_slug,
    _strip_code_fence,
    run_fanout,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    (v / "cac" / "meeting-notes").mkdir(parents=True)
    note = v / "cac" / "meeting-notes" / "2026-05-26-alco-monthly.md"
    note.write_text(
        "---\ndate: 2026-05-26\ntype: meeting-note\ncommittee: CAC\n---\n"
        "# ALCO Monthly\n\n## Attendees\n- CFO\n- CRO\n\n"
        "## Decisions\n- Approved revised LCR target of 115%\n"
        "BICL covenant DSCR is 1.62x as of Apr.\n",
        encoding="utf-8",
    )
    return v


@pytest.fixture
def event() -> MeetingNoteLandedEvent:
    return MeetingNoteLandedEvent(
        vault_path="cac/meeting-notes/2026-05-26-alco-monthly.md",
        dept="cac",
        sha256="abc123def" + "0" * 55,
        size_bytes=200,
    )


def _make_invoker(per_prompt_response: dict[str, str]):
    """Return an async LLM invoker that maps prompt-keyword -> raw response string."""
    async def _invoke(prompt: str) -> str:
        for key, resp in per_prompt_response.items():
            if key in prompt:
                return resp
        return "{}"
    return _invoke


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_strip_code_fence_removes_json_fence():
    src = "```json\n{\"a\": 1}\n```"
    assert _strip_code_fence(src) == '{"a": 1}'


def test_strip_code_fence_handles_plain_fence():
    src = "```\n{\"a\": 1}\n```"
    assert _strip_code_fence(src) == '{"a": 1}'


def test_strip_code_fence_passthrough_when_no_fence():
    assert _strip_code_fence('{"a": 1}') == '{"a": 1}'


def test_safe_json_returns_empty_on_bad():
    assert _safe_json("not json at all") == {}


def test_safe_json_parses_fenced():
    out = _safe_json("```json\n{\"x\": 2}\n```")
    assert out == {"x": 2}


def test_clamp_confidence_bounds():
    assert _clamp_confidence(0.5) == 0.5
    assert _clamp_confidence(1.5) == 1.0
    assert _clamp_confidence(-0.2) == 0.0
    assert _clamp_confidence("0.7") == 0.7
    assert _clamp_confidence("garbage", default=0.4) == 0.4


def test_safe_slug_fallback():
    assert _safe_slug("Audit Committee", "fallback") == "audit-committee"
    assert _safe_slug("", "fallback") == "fallback"
    assert _safe_slug("   ", "fb") == "fb"


# ---------------------------------------------------------------------------
# Extractor unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entities_extractor_parses_response(event: MeetingNoteLandedEvent):
    invoker = _make_invoker({
        "extract named entities": json.dumps({"entities": [
            {"slug": "bicl", "display_name": "BICL", "kind": "company",
             "one_liner": "Brooker International Co Ltd", "confidence": 0.92},
            {"slug": "lcr", "display_name": "LCR", "kind": "concept",
             "one_liner": "Liquidity Coverage Ratio", "confidence": 0.8},
        ]}),
    })
    out = await EXTRACTORS["entities"](
        event=event, body="x", source_run_id="srun_test", today=date(2026, 5, 26), llm=invoker,
    )
    assert len(out) == 2
    slugs = {Path(m.target_vault_path).stem for m in out}
    assert slugs == {"bicl", "lcr"}
    bicl = next(m for m in out if "bicl" in m.target_vault_path)
    assert bicl.confidence == 0.92
    assert "Brooker International Co Ltd" in bicl.draft_content
    assert "TL;DR for Agents" in bicl.draft_content


@pytest.mark.asyncio
async def test_decisions_extractor_dates_filenames(event: MeetingNoteLandedEvent):
    invoker = _make_invoker({
        "extract committee decisions": json.dumps({"decisions": [
            {"slug": "raise-lcr-target", "title": "Raise LCR target",
             "outcome": "LCR target raised to 115%", "rationale": "Buffer above regulatory min",
             "binding_constraint": "LCR >= 115%", "confidence": 0.9},
        ]}),
    })
    out = await EXTRACTORS["decisions"](
        event=event, body="x", source_run_id="srun", today=date(2026, 5, 26), llm=invoker,
    )
    assert len(out) == 1
    m = out[0]
    assert m.target_vault_path == "cac/decisions/2026-05-26-raise-lcr-target.md"
    assert "Decision: Raise LCR target" in m.draft_content
    assert "LCR >= 115%" in m.draft_content


@pytest.mark.asyncio
async def test_trends_extractor_filters_max_8(event: MeetingNoteLandedEvent):
    big_trends = [
        {"slug": f"m{i}", "metric_name": f"Metric {i}", "value": f"{i}%",
         "as_of": "2026-05-26", "direction": "up", "confidence": 0.5}
        for i in range(15)
    ]
    invoker = _make_invoker({
        "extract quantitative metric": json.dumps({"trends": big_trends}),
    })
    out = await EXTRACTORS["trends"](
        event=event, body="x", source_run_id="srun", today=date(2026, 5, 26), llm=invoker,
    )
    assert len(out) == 8


@pytest.mark.asyncio
async def test_source_summary_skips_empty_abstract(event: MeetingNoteLandedEvent):
    invoker = _make_invoker({
        "single short source-summary": json.dumps({"summary": {
            "title": "ALCO Monthly", "abstract": "", "key_terms": [], "confidence": 0.6,
        }}),
    })
    out = await EXTRACTORS["source_summary"](
        event=event, body="x", source_run_id="srun", today=date(2026, 5, 26), llm=invoker,
    )
    assert out == []


@pytest.mark.asyncio
async def test_source_summary_writes_when_abstract_present(event: MeetingNoteLandedEvent):
    invoker = _make_invoker({
        "single short source-summary": json.dumps({"summary": {
            "title": "ALCO Monthly", "abstract": "The committee reviewed LCR and approved a target raise.",
            "key_terms": ["LCR", "ALCO", "policy"], "confidence": 0.75,
        }}),
    })
    out = await EXTRACTORS["source_summary"](
        event=event, body="x", source_run_id="srun", today=date(2026, 5, 26), llm=invoker,
    )
    assert len(out) == 1
    assert "approved a target raise" in out[0].draft_content
    assert out[0].confidence == 0.75


@pytest.mark.asyncio
async def test_index_update_does_not_call_llm(event: MeetingNoteLandedEvent):
    called = []
    async def _should_not_be_called(p: str) -> str:
        called.append(p)
        return "{}"
    out = await EXTRACTORS["index_update"](
        event=event, body="x", source_run_id="srun", today=date(2026, 5, 26), llm=_should_not_be_called,
    )
    assert called == []
    assert len(out) == 1
    assert out[0].target_vault_path == "cac/index.md"
    assert out[0].confidence == 0.95


@pytest.mark.asyncio
async def test_extractor_with_bad_json_returns_empty(event: MeetingNoteLandedEvent):
    async def _garbage(p: str) -> str:
        return "I refuse to output JSON, here is some prose."
    out = await EXTRACTORS["entities"](
        event=event, body="x", source_run_id="srun", today=date(2026, 5, 26), llm=_garbage,
    )
    assert out == []


# ---------------------------------------------------------------------------
# End-to-end fanout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_fanout_aggregates_extractor_outputs(vault: Path, tmp_path: Path, event: MeetingNoteLandedEvent):
    staging = tmp_path / "staging"
    invoker = _make_invoker({
        "extract named entities": json.dumps({"entities": [
            {"slug": "bicl", "display_name": "BICL", "kind": "company",
             "one_liner": "Brooker International", "confidence": 0.9},
        ]}),
        "extract committee decisions": json.dumps({"decisions": [
            {"slug": "raise-lcr", "title": "Raise LCR", "outcome": "115%",
             "rationale": "", "binding_constraint": "", "confidence": 0.85},
        ]}),
        "extract quantitative metric": json.dumps({"trends": [
            {"slug": "lcr", "metric_name": "LCR", "value": "115%",
             "as_of": "2026-05-26", "direction": "up", "confidence": 0.8},
        ]}),
        "single short source-summary": json.dumps({"summary": {
            "title": "ALCO Monthly", "abstract": "Reviewed LCR, raised target.",
            "key_terms": ["LCR"], "confidence": 0.7,
        }}),
    })
    result = await run_fanout(
        event, staging_path=str(staging), vault_root=str(vault),
        today=date(2026, 5, 26), llm_invoker=invoker,
    )
    # 1 entity + 1 decision + 1 trend + 1 source-summary + 1 index-update
    assert len(result.proposal_ids) == 5
    targets = set()
    for pid in result.proposal_ids:
        m = json.loads(
            (staging / "pending" / pid / "manifest.json").read_text(encoding="utf-8")
        )
        targets.add(m["target_vault_path"])
    assert "cac/entities/bicl.md" in targets
    assert "cac/decisions/2026-05-26-raise-lcr.md" in targets
    assert "cac/trends/2026-05-26-lcr.md" in targets
    assert "cac/index.md" in targets
    assert any("source-summaries/" in t for t in targets)


@pytest.mark.asyncio
async def test_run_fanout_isolates_extractor_exceptions(vault: Path, tmp_path: Path, event: MeetingNoteLandedEvent, monkeypatch):
    staging = tmp_path / "staging"
    async def _boom(**kwargs):
        raise RuntimeError("intentional test failure")
    monkeypatch.setitem(EXTRACTORS, "decisions", _boom)
    invoker = _make_invoker({})  # all other extractors will get "{}" and return empty
    result = await run_fanout(
        event, staging_path=str(staging), vault_root=str(vault),
        today=date(2026, 5, 26), llm_invoker=invoker,
    )
    # entities/trends/source_summary returned [] -> skipped; decisions raised -> skipped;
    # index_update is mechanical -> 1 manifest
    assert "decisions" in result.skipped_extractors
    assert len(result.proposal_ids) == 1
    m = json.loads(
        (staging / "pending" / result.proposal_ids[0] / "manifest.json").read_text(encoding="utf-8")
    )
    assert m["target_vault_path"] == "cac/index.md"


@pytest.mark.asyncio
async def test_run_fanout_missing_file_returns_empty(tmp_path: Path):
    staging = tmp_path / "staging"
    bad_event = MeetingNoteLandedEvent(
        vault_path="cac/meeting-notes/does-not-exist.md",
        dept="cac", sha256="x" * 64, size_bytes=0,
    )
    result = await run_fanout(
        bad_event, staging_path=str(staging),
        vault_root=str(tmp_path / "missing-vault"),
        llm_invoker=_make_invoker({}),
    )
    assert result.proposal_ids == []
