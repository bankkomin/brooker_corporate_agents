"""Unit tests for excel_navigator node."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from services.cac_orchestrator.src.nodes.excel_navigator import excel_navigator

_SCHEMA = {
    "filename": "ALCO_Tracker.xlsx",
    "tabs": [
        {
            "name": "Funding Facilities",
            "header_row": 7,
            "rows": [
                {
                    "row": 8,
                    "label": "SCB Facility",
                    "columns": {
                        "B": "Facility Name",
                        "C": "Limit",
                        "D": "Drawn Amount",
                        "E": "Covenant Threshold",
                    },
                }
            ],
        }
    ],
}


@pytest.fixture
def schema_path(tmp_path: Path) -> str:
    p = tmp_path / "alco_tracker.json"
    p.write_text(json.dumps(_SCHEMA), encoding="utf-8")
    return str(p)


async def test_maps_to_correct_cell(schema_path: str) -> None:
    """E8 resolves to the human-readable navigation string."""
    state = {"proposed_cell": "E8"}
    result = await excel_navigator(state, schema_path=schema_path)
    assert result["excel_nav"] == (
        "ALCO_Tracker.xlsx → Tab: Funding Facilities → Row 8 → Column E: Covenant Threshold"
    )


async def test_returns_none_when_no_proposed_cell(schema_path: str) -> None:
    """No proposed_cell in state returns None."""
    state: dict = {}
    result = await excel_navigator(state, schema_path=schema_path)
    assert result["excel_nav"] is None


async def test_unknown_cell_fallback(schema_path: str) -> None:
    """Cell not in schema falls back to 'filename → Cell Z99'."""
    state = {"proposed_cell": "Z99"}
    result = await excel_navigator(state, schema_path=schema_path)
    assert result["excel_nav"] == "ALCO_Tracker.xlsx → Cell Z99"


async def test_invalid_cell_format(schema_path: str) -> None:
    """Non-parseable cell reference handled gracefully (no digit found)."""
    state = {"proposed_cell": "invalid"}
    result = await excel_navigator(state, schema_path=schema_path)
    # Should not raise; returns a fallback or None-safe result
    assert "excel_nav" in result


async def test_missing_schema_file(tmp_path: Path) -> None:
    """Non-existent schema file handled gracefully."""
    bad_path = str(tmp_path / "no_such_file.json")
    state = {"proposed_cell": "E8"}
    result = await excel_navigator(state, schema_path=bad_path)
    assert "excel_nav" in result
    # filename defaults to "Unknown" when schema can't be loaded
    assert result["excel_nav"] is not None


async def test_correct_column_label(schema_path: str) -> None:
    """Column E maps to 'Covenant Threshold' from the schema."""
    state = {"proposed_cell": "E8"}
    result = await excel_navigator(state, schema_path=schema_path)
    assert result["excel_nav"] is not None
    assert "Covenant Threshold" in result["excel_nav"]
