"""Unit tests for services/shared/chart_render.py.

Tests cover:
- All five chart kinds render to valid PNG bytes
- Annotations do not crash line rendering
- validate_chart_spec rejects bad input and coerces numeric strings
- save_chart writes a real file
- Brooker palette colour is present in rendered output

External dependencies: matplotlib, Pillow (PIL).
No network I/O; no service calls; no database.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _is_png(data: bytes) -> bool:
    return data[:8] == _PNG_MAGIC


# ---------------------------------------------------------------------------
# Render tests
# ---------------------------------------------------------------------------


def test_bar_chart_renders_png():
    """3-series grouped bar chart returns valid PNG bytes."""
    from services.shared.chart_render import render_chart_png

    spec = {
        "kind": "bar",
        "title": "Quarterly Revenue",
        "x_label": "Quarter",
        "y_label": "THB millions",
        "series": [
            {"name": "Revenue", "data": [120, 130, 145]},
            {"name": "EBITDA", "data": [40, 50, 60]},
            {"name": "Net Profit", "data": [20, 28, 35]},
        ],
        "x_labels": ["Q1", "Q2", "Q3"],
        "palette": "brooker",
    }
    result = render_chart_png(spec)
    assert isinstance(result, bytes)
    assert _is_png(result), "Returned bytes do not start with PNG magic"
    assert len(result) > 1000, "PNG is suspiciously small"


def test_line_chart_with_annotations():
    """Line chart with annotations renders without crashing."""
    from services.shared.chart_render import render_chart_png

    spec = {
        "kind": "line",
        "title": "Liquidity Runway (months)",
        "series": [
            {"name": "Runway", "data": [14, 15, 13, 12, 10, 9]},
        ],
        "x_labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        "annotations": [
            {"x": "May", "y": 10, "text": "watch"},
            {"x": "Jun", "y": 9, "text": "breach threshold"},
        ],
        "palette": "brooker",
    }
    result = render_chart_png(spec)
    assert isinstance(result, bytes)
    assert _is_png(result)


def test_pie_chart_with_explicit_labels():
    """Pie chart with labels in series[0] renders and returns non-empty bytes."""
    from services.shared.chart_render import render_chart_png

    spec = {
        "kind": "pie",
        "title": "Capital Allocation Mix",
        "series": [
            {
                "name": "Allocation",
                "data": [35, 25, 20, 20],
                "labels": ["Digital Assets", "Advisory", "VCC", "Cash"],
            }
        ],
        "palette": "brooker",
    }
    result = render_chart_png(spec)
    assert isinstance(result, bytes)
    assert len(result) > 0
    assert _is_png(result)


def test_stacked_bar_with_multiple_series():
    """Stacked bar with 2 series renders correctly."""
    from services.shared.chart_render import render_chart_png

    spec = {
        "kind": "stacked_bar",
        "title": "Funding Mix",
        "series": [
            {"name": "Drawn", "data": [200, 220, 210]},
            {"name": "Available", "data": [300, 280, 290]},
        ],
        "x_labels": ["Apr", "May", "Jun"],
        "palette": "muted",
    }
    result = render_chart_png(spec)
    assert _is_png(result)


def test_horizontal_bar():
    """Horizontal bar chart smoke test."""
    from services.shared.chart_render import render_chart_png

    spec = {
        "kind": "horizontal_bar",
        "title": "Department Headcount",
        "series": [
            {"name": "Headcount", "data": [12, 8, 15, 6]},
        ],
        "x_labels": ["IB", "Risk", "IT", "HR"],
    }
    result = render_chart_png(spec)
    assert _is_png(result)


def test_save_chart_writes_file():
    """save_chart writes a PNG file that exists and is a valid PNG."""
    from services.shared.chart_render import render_chart_png, save_chart

    spec = {
        "kind": "bar",
        "title": "Test Save",
        "series": [{"name": "X", "data": [1, 2, 3]}],
        "x_labels": ["a", "b", "c"],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "subdir" / "test_chart.png"
        returned = save_chart(spec, out)
        assert returned == out
        assert out.exists(), "save_chart did not create the file"
        raw = out.read_bytes()
        assert _is_png(raw), "Written file is not a valid PNG"
        # Verify file content is a valid PNG (byte-identical comparison is
        # unreliable due to timestamp bytes embedded by some PNG encoders)
        assert len(raw) > 1000, "Saved PNG is suspiciously small"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_validate_rejects_missing_kind():
    """validate_chart_spec raises ValueError when 'kind' is absent."""
    from services.shared.chart_render import validate_chart_spec

    with pytest.raises(ValueError, match="kind"):
        validate_chart_spec({"series": [{"name": "X", "data": [1, 2]}]})


def test_validate_rejects_missing_series():
    """validate_chart_spec raises ValueError when 'series' is absent."""
    from services.shared.chart_render import validate_chart_spec

    with pytest.raises(ValueError, match="series"):
        validate_chart_spec({"kind": "bar"})


def test_validate_rejects_series_length_mismatch():
    """series[0]['data'] length != x_labels length raises ValueError."""
    from services.shared.chart_render import validate_chart_spec

    with pytest.raises(ValueError, match="x_labels"):
        validate_chart_spec(
            {
                "kind": "bar",
                "series": [{"name": "Rev", "data": [1, 2, 3]}],
                "x_labels": ["Q1", "Q2"],  # 2 labels but 3 data points
            }
        )


def test_validate_coerces_numeric_strings():
    """string-typed data values are coerced to float without raising."""
    from services.shared.chart_render import validate_chart_spec

    result = validate_chart_spec(
        {
            "kind": "line",
            "series": [{"name": "Rev", "data": ["120", "130", "145.5"]}],
            "x_labels": ["Q1", "Q2", "Q3"],
        }
    )
    coerced = result["series"][0]["data"]  # type: ignore[index]
    assert coerced == [120.0, 130.0, 145.5]
    assert all(isinstance(v, float) for v in coerced)


def test_validate_rejects_invalid_kind():
    """An unrecognised kind raises a clear ValueError."""
    from services.shared.chart_render import validate_chart_spec

    with pytest.raises(ValueError, match="kind"):
        validate_chart_spec({"kind": "donut", "series": [{"data": [1]}]})


def test_validate_rejects_un_coercible_data():
    """Non-numeric data values that can't be coerced raise ValueError."""
    from services.shared.chart_render import validate_chart_spec

    with pytest.raises(ValueError, match="coerced to float"):
        validate_chart_spec(
            {
                "kind": "bar",
                "series": [{"name": "X", "data": ["not_a_number"]}],
            }
        )


# ---------------------------------------------------------------------------
# Palette pixel test
# ---------------------------------------------------------------------------


def test_brooker_palette_used():
    """Render a bar chart and verify at least one pixel matches Brooker navy #0F3D5C."""
    from services.shared.chart_render import render_chart_png

    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow is not installed; skipping pixel-level palette test")

    spec = {
        "kind": "bar",
        "title": "Palette Test",
        "series": [{"name": "A", "data": [100, 200, 150]}],
        "x_labels": ["X", "Y", "Z"],
        "palette": "brooker",
    }
    png_bytes = render_chart_png(spec, width_px=800, height_px=400, dpi=80)

    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    # getdata() is deprecated in Pillow 14; list(img.getdata()) still works but
    # using getpixel iteration avoids the warning on newer Pillow builds.
    width, height = img.size
    pixels = [img.getpixel((x, y)) for y in range(height) for x in range(width)]

    # Brooker navy: R=15, G=61, B=92
    target_r, target_g, target_b = 0x0F, 0x3D, 0x5C
    tolerance = 10  # allow minor anti-aliasing shift

    found = any(
        abs(r - target_r) <= tolerance
        and abs(g - target_g) <= tolerance
        and abs(b - target_b) <= tolerance
        for r, g, b in pixels
    )
    assert found, (
        f"Brooker navy #{target_r:02X}{target_g:02X}{target_b:02X} "
        "was not found in the rendered PNG — palette may not be applied"
    )
