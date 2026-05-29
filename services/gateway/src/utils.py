"""Shared utility functions for the gateway service."""
from __future__ import annotations

from typing import Any


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a database row dict to JSON-safe dict. Handles datetime -> ISO string."""
    result: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


# SQL fragment for ordering escalations by urgency (not alphabetic). Use this
# instead of `ORDER BY severity ASC` — the text column would otherwise sort
# {critical, high, low, medium} lexicographically, placing 'low' before 'medium'.
SEVERITY_ORDER_SQL = (
    "CASE severity "
    "WHEN 'critical' THEN 0 "
    "WHEN 'high'     THEN 1 "
    "WHEN 'medium'   THEN 2 "
    "WHEN 'low'      THEN 3 "
    "ELSE 4 END"
)
