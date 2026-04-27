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
        return {"excel_nav": None, "old_value": "(current value not available)"}

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
        return {
            "excel_nav": f"{filename} → Cell {proposed_cell}",
            "old_value": "(current value not available)",
        }

    # If proposed_tab is set, restrict search to that tab only; otherwise
    # search all tabs (original fallback behaviour).
    proposed_tab = state.get("proposed_tab", "")

    for tab in schema.get("tabs", []):
        tab_name = tab.get("name", "")
        # FIX 12: skip tabs that don't match proposed_tab when it is provided
        if proposed_tab and tab_name != proposed_tab:
            continue
        for row_def in tab.get("rows", []):
            if row_def.get("row") == row_num:
                col_label = row_def.get("columns", {}).get(col_match, col_match)
                nav = (
                    f"{filename} → Tab: {tab_name} → "
                    f"Row {row_num} → Column {col_match}: {col_label}"
                )
                logger.info("excel_nav_resolved", nav=nav)
                # FIX 5: expose old_value from schema metadata if available,
                # otherwise use a safe sentinel so staging_writer/validate_proposal
                # always find a non-None value in state.
                old_value = row_def.get("columns_current_values", {}).get(
                    col_match, "(current value not available)"
                )
                return {"excel_nav": nav, "old_value": old_value}

    # Fallback: no matching tab/row found
    nav = f"{filename} → Cell {proposed_cell}"
    logger.info("excel_nav_fallback", nav=nav)
    return {"excel_nav": nav, "old_value": "(current value not available)"}
