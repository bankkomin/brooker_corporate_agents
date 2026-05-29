"""Tests for B5 daily-log drafter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.daily_log_drafter import (
    _count_proposals,
    draft_daily_log,
    render_daily_log_md,
)


@dataclass
class _FakeDecision:
    proposal_id: str
    agent_id: str
    action: str
    signal_strength: float


def test_render_daily_log_md_minimal():
    out = render_daily_log_md(
        dept_id="cac",
        target_date=date(2026, 5, 25),
        decisions=[],
        gaps=[],
        proposal_count=0,
    )
    assert "# Daily Log — cac — 2026-05-25" in out
    assert "Proposals created: 0" in out
    assert "type: daily-log" in out
    assert "vault_automation" in out
    # Empty sections omitted
    assert "## Approval decisions" not in out
    assert "## Knowledge gaps" not in out


def test_render_daily_log_md_with_activity():
    decisions = [
        _FakeDecision("chg_001", "cfo-agent", "approved", 0.92),
        _FakeDecision("chg_002", "alm-agent", "edited", 0.55),
    ]
    gaps = [
        {"agent_id": "liquidity-agent", "query": "what is the latest LCR?", "hit_count": 0},
    ]
    out = render_daily_log_md(
        dept_id="cac",
        target_date=date(2026, 5, 25),
        decisions=decisions,
        gaps=gaps,
        proposal_count=2,
    )
    assert "## Approval decisions" in out
    assert "`chg_001` — approved (signal=0.92)" in out
    assert "## Knowledge gaps" in out
    assert "liquidity-agent" in out
    assert "latest LCR" in out


@pytest.mark.asyncio
async def test_count_proposals_returns_zero_on_missing_table(monkeypatch):
    # Simulate the proposals table not existing yet (pre-bootstrap state)
    import asyncpg
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow.side_effect = asyncpg.UndefinedTableError("relation does not exist")
    # acquire() returns an async context manager
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=cm)
    n = await _count_proposals(pool, "cac", date(2026, 5, 25))
    assert n == 0


@pytest.mark.asyncio
async def test_draft_daily_log_skips_on_no_activity(monkeypatch, tmp_path: Path):
    pool = MagicMock()
    async def empty_decisions(*args, **kwargs):
        return []
    async def empty_gaps(*args, **kwargs):
        return []
    monkeypatch.setattr("src.daily_log_drafter.get_recent_decisions", empty_decisions)
    monkeypatch.setattr("src.daily_log_drafter.get_recent_knowledge_gaps", empty_gaps)
    async def zero_proposals(*args, **kwargs):
        return 0
    monkeypatch.setattr("src.daily_log_drafter._count_proposals", zero_proposals)
    result = await draft_daily_log(
        "cac", pool, staging_path=str(tmp_path), target_date=date(2026, 5, 25),
    )
    assert result is None
    # No staging directory should have been created
    assert not (tmp_path / "pending").exists()


@pytest.mark.asyncio
async def test_draft_daily_log_writes_when_activity_exists(monkeypatch, tmp_path: Path):
    pool = MagicMock()
    async def decisions(*args, **kwargs):
        return [_FakeDecision("chg_001", "x", "approved", 0.8)]
    async def gaps(*args, **kwargs):
        return []
    async def proposals(*args, **kwargs):
        return 3
    monkeypatch.setattr("src.daily_log_drafter.get_recent_decisions", decisions)
    monkeypatch.setattr("src.daily_log_drafter.get_recent_knowledge_gaps", gaps)
    monkeypatch.setattr("src.daily_log_drafter._count_proposals", proposals)

    pid = await draft_daily_log(
        "cac", pool, staging_path=str(tmp_path), target_date=date(2026, 5, 25),
    )
    assert pid is not None
    proposal_dir = tmp_path / "pending" / pid
    assert (proposal_dir / "manifest.json").is_file()
    assert (proposal_dir / "draft.md").is_file()
    persisted = json.loads((proposal_dir / "manifest.json").read_text(encoding="utf-8"))
    assert persisted["target_vault_path"] == "cac/daily-logs/2026-05-25.md"
    assert persisted["operation"] == "create"
    assert persisted["dept"] == "cac"
    assert persisted["agent"] == "reflection-engine.daily_log_drafter"
    assert persisted["proposal_source"] == "vault_automation"
    draft = (proposal_dir / "draft.md").read_text(encoding="utf-8")
    assert "Proposals created: 3" in draft
    assert "chg_001" in draft
