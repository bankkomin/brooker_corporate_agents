"""Excel navigation node — maps proposed changes to spreadsheet cells."""
from __future__ import annotations

import json

import structlog

logger = structlog.get_logger("cac-orchestrator.excel_nav")


def _load_schema(schema_path: str) -> dict:
    """Load Excel schema from JSON config file."""
    try:
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("excel_schema_load_failed", path=schema_path, error=str(exc))
        return {}


async def excel_navigator(state: dict, *, schema_path: str) -> dict:
    """Map proposed cell to human-readable navigation string.

    Returns {"excel_nav": str | None}.
    """
    proposed_cell = state.get("proposed_cell")
    if not proposed_cell:
        return {"excel_nav": None}

    schema = _load_schema(schema_path)
    filename = schema.get("filename", "Unknown")

    # Parse cell reference (e.g., "E8" -> column "E", row 8)
    col_match = ""
    row_num = 0
    for i, ch in enumerate(proposed_cell):
        if ch.isdigit():
            col_match = proposed_cell[:i]
            row_num = int(proposed_cell[i:])
            break

    if not col_match or not row_num:
        logger.warning("invalid_cell_reference", cell=proposed_cell)
        return {"excel_nav": f"{filename} → Cell {proposed_cell}"}

    # Find the matching tab, row, and column label
    for tab in schema.get("tabs", []):
        tab_name = tab.get("name", "")
        for row_def in tab.get("rows", []):
            if row_def.get("row") == row_num:
                col_label = row_def.get("columns", {}).get(col_match, col_match)
                nav = (
                    f"{filename} → Tab: {tab_name} → "
                    f"Row {row_num} → Column {col_match}: {col_label}"
                )
                logger.info("excel_nav_resolved", nav=nav)
                return {"excel_nav": nav}

    # Fallback: no matching tab/row found
    nav = f"{filename} → Cell {proposed_cell}"
    logger.info("excel_nav_fallback", nav=nav)
    return {"excel_nav": nav}
