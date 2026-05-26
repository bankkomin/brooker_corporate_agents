"""Tests for B3 meeting fan-out scaffold."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from services.cac_orchestrator.src.meeting_fanout import (
    EXTRACTORS,
    FanoutResult,
    MeetingNoteLandedEvent,
    run_fanout,
)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    (v / "cac" / "meeting-notes").mkdir(parents=True)
    note = v / "cac" / "meeting-notes" / "2026-05-26-alco-monthly.md"
    note.write_text(
        "---\ndate: 2026-05-26\ntype: meeting-note\ncommittee: CAC\n---\n"
        "# ALCO Monthly\n\n## Attendees\n- CFO\n- CRO\n\n"
        "## Decisions\n- Approved revised LCR target of 115%\n",
        encoding="utf-8",
    )
    return v


def test_extractors_registered():
    assert set(EXTRACTORS.keys()) == {
        "entities", "decisions", "trends", "source_summary", "index_update",
    }


def test_index_update_is_high_confidence_stub_others_low():
    event = MeetingNoteLandedEvent(
        vault_path="cac/meeting-notes/2026-05-26-x.md",
        dept="cac", sha256="a" * 64, size_bytes=100,
    )
    m_idx = EXTRACTORS["index_update"](
        event=event, body="x", source_run_id="srun_test", today=date(2026, 5, 26),
    )
    m_ent = EXTRACTORS["entities"](
        event=event, body="x", source_run_id="srun_test", today=date(2026, 5, 26),
    )
    assert m_idx.confidence == 0.95
    assert m_idx.operation == "append"
    assert m_ent.confidence == 0.0  # stub
    assert m_ent.operation == "create"
    # All extractor outputs share the same source_run_id
    assert m_idx.source_run_id == m_ent.source_run_id


@pytest.mark.asyncio
async def test_run_fanout_writes_all_extractors(vault: Path, tmp_path: Path):
    staging = tmp_path / "staging"
    event = MeetingNoteLandedEvent(
        vault_path="cac/meeting-notes/2026-05-26-alco-monthly.md",
        dept="cac",
        sha256="abc123def456" + "0" * 52,
        size_bytes=200,
    )
    result = await run_fanout(
        event,
        staging_path=str(staging),
        vault_root=str(vault),
        today=date(2026, 5, 26),
    )
    assert isinstance(result, FanoutResult)
    assert len(result.proposal_ids) == 5
    assert result.skipped_extractors == []
    assert result.source_run_id.startswith("meetfan_")

    # All five manifests share the run_id
    run_ids = set()
    targets = set()
    for pid in result.proposal_ids:
        manifest = json.loads(
            (staging / "pending" / pid / "manifest.json").read_text(encoding="utf-8")
        )
        run_ids.add(manifest["source_run_id"])
        targets.add(manifest["target_vault_path"])
        assert manifest["extracted_from"] == "cac/meeting-notes/2026-05-26-alco-monthly.md"
        assert manifest["dept"] == "cac"
        assert manifest["proposal_source"] == "vault_automation"
    assert len(run_ids) == 1
    # Targets cover the 5 distinct artifact types
    assert any("entities" in t for t in targets)
    assert any("decisions" in t for t in targets)
    assert any("trends" in t for t in targets)
    assert any("source-summaries" in t for t in targets)
    assert any("index.md" in t for t in targets)


@pytest.mark.asyncio
async def test_run_fanout_missing_file_returns_empty(tmp_path: Path):
    staging = tmp_path / "staging"
    event = MeetingNoteLandedEvent(
        vault_path="cac/meeting-notes/does-not-exist.md",
        dept="cac", sha256="x" * 64, size_bytes=0,
    )
    result = await run_fanout(
        event, staging_path=str(staging), vault_root=str(tmp_path / "missing-vault"),
    )
    assert result.proposal_ids == []
    assert not (staging / "pending").exists()


@pytest.mark.asyncio
async def test_run_fanout_isolates_extractor_failures(vault: Path, tmp_path: Path, monkeypatch):
    """If one extractor raises, the others still produce manifests."""
    staging = tmp_path / "staging"

    def bad_extractor(**kwargs):
        raise RuntimeError("intentional test failure")

    monkeypatch.setitem(EXTRACTORS, "trends", bad_extractor)
    event = MeetingNoteLandedEvent(
        vault_path="cac/meeting-notes/2026-05-26-alco-monthly.md",
        dept="cac",
        sha256="abc" + "0" * 61,
        size_bytes=200,
    )
    result = await run_fanout(
        event, staging_path=str(staging), vault_root=str(vault),
    )
    assert "trends" in result.skipped_extractors
    assert len(result.proposal_ids) == 4
