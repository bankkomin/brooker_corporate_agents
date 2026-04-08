"""Unit tests for gateway shared utility functions."""
from __future__ import annotations

from datetime import datetime

from services.gateway.src.utils import serialize_row


class TestSerializeRow:
    """Tests for serialize_row()."""

    def test_datetime_converted_to_iso_string(self) -> None:
        """datetime values are converted to ISO 8601 strings."""
        dt = datetime(2026, 3, 1, 12, 30, 0)
        row = {"created_at": dt, "id": "chg_0001"}

        result = serialize_row(row)

        assert result["created_at"] == dt.isoformat()
        assert isinstance(result["created_at"], str)

    def test_non_datetime_values_pass_through_unchanged(self) -> None:
        """Non-datetime values are returned as-is."""
        row = {
            "id": "chg_0001",
            "confidence": 0.91,
            "status": "pending",
            "count": 42,
            "flag": True,
            "nothing": None,
        }

        result = serialize_row(row)

        assert result["id"] == "chg_0001"
        assert result["confidence"] == 0.91
        assert result["status"] == "pending"
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["nothing"] is None

    def test_mixed_row_with_datetime_and_other_types(self) -> None:
        """Rows with a mix of datetime and other fields are serialised correctly."""
        dt = datetime(2026, 1, 15, 8, 0, 0)
        row = {
            "id": "chg_0002",
            "created_at": dt,
            "dept": "cac",
            "confidence": 0.75,
        }

        result = serialize_row(row)

        assert result["id"] == "chg_0002"
        assert result["created_at"] == dt.isoformat()
        assert result["dept"] == "cac"
        assert result["confidence"] == 0.75

    def test_empty_row_returns_empty_dict(self) -> None:
        """An empty input row returns an empty dict."""
        result = serialize_row({})
        assert result == {}
