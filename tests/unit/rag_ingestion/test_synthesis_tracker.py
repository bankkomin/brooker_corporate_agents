"""Tests for B4 synthesis_tracker."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.rag_ingestion.src.synthesis_tracker import (
    EntityMention,
    SynthesisCandidate,
    extract_entities,
    find_synthesis_candidates,
    load_thresholds,
    record_mentions,
    threshold_for_dept,
)


def test_extract_entities_picks_pascal_runs():
    text = "The Audit Committee reviewed the BICL portfolio and updated CAR levels."
    out = {slug for slug, _, _ in extract_entities(text)}
    assert "audit-committee" in out
    assert "bicl" in out  # acronym allowlist
    assert "car" in out


def test_extract_entities_skips_stopwords():
    text = "The Operations Department is The Sole Owner"
    out = {disp for _, disp, _ in extract_entities(text)}
    # "The Sole Owner" starts with "The" -> excluded as stopword-led
    assert "The Sole Owner" not in out
    # "Operations Department" is valid
    assert "Operations Department" in out


def test_extract_entities_ignores_unknown_acronyms():
    text = "We discussed XYZ and ABC during the meeting"
    out = {disp for _, disp, _ in extract_entities(text)}
    assert "XYZ" not in out
    assert "ABC" not in out


def test_load_thresholds_falls_back_when_missing(tmp_path: Path):
    t = load_thresholds(tmp_path / "no-such.json")
    assert t["default"] == 3
    assert t["per_dept"] == {}


def test_load_thresholds_parses_real_config():
    cfg_path = Path(__file__).resolve().parents[3] / "config" / "synthesis_thresholds.json"  # tests/unit/rag_ingestion -> repo root
    if not cfg_path.exists():
        pytest.skip("config not in checkout")
    t = load_thresholds(cfg_path)
    assert t["default"] == 3
    assert t["per_dept"]["regulations"] == 2
    assert t["per_dept"]["research"] == 4


def test_threshold_for_dept_resolution():
    t = {"default": 3, "per_dept": {"regulations": 2, "research": 4}}
    assert threshold_for_dept("regulations", t) == 2
    assert threshold_for_dept("research", t) == 4
    assert threshold_for_dept("hr", t) == 3  # falls back to default


@pytest.mark.asyncio
async def test_record_mentions_inserts_rows():
    pool = MagicMock()
    conn = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=cm)

    chunks = [
        {"id": "c1", "text": "The Audit Committee reviewed BICL holdings"},
        {"id": "c2", "text": "Capital Allocation requires CAR > 8%"},
    ]
    n = await record_mentions(pool, chunks=chunks, source_doc="ALCO_Tracker.xlsx", dept="cac")
    assert n > 0
    # executemany called once with all rows
    conn.executemany.assert_called_once()
    args = conn.executemany.call_args
    rows = args[0][1]
    assert any(r[0] == "audit-committee" for r in rows)
    assert any(r[0] == "bicl" for r in rows)


@pytest.mark.asyncio
async def test_record_mentions_swallows_db_errors(monkeypatch):
    pool = MagicMock()
    conn = AsyncMock()
    conn.executemany.side_effect = RuntimeError("table missing")
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=cm)

    n = await record_mentions(
        pool, chunks=[{"id": "c1", "text": "Audit Committee"}], source_doc="x", dept="cac",
    )
    assert n == 0  # graceful


@pytest.mark.asyncio
async def test_find_synthesis_candidates_filters_by_threshold():
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetch.return_value = [
        {"entity": "audit-committee", "dept": "regulations", "source_count": 4},
        {"entity": "bicl", "dept": "cac", "source_count": 2},
        {"entity": "noise", "dept": "research", "source_count": 3},
    ]
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.acquire = MagicMock(return_value=cm)

    t = {"default": 3, "per_dept": {"regulations": 2, "research": 4}}
    out = await find_synthesis_candidates(pool, thresholds=t)
    entities = {c.entity for c in out}
    assert "audit-committee" in entities  # 4 >= 2 regulations threshold
    assert "bicl" not in entities         # 2 < 3 default
    assert "noise" not in entities        # 3 < 4 research threshold
