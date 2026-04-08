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
