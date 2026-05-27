"""Server-side chart rendering to PNG bytes via matplotlib (headless).

Renders bar, line, pie, stacked_bar, and horizontal_bar charts from a
ChartSpec dict. Intended for embedding into Word/PowerPoint documents via
python-docx / python-pptx; callers receive raw PNG bytes or write to a file.

Usage:
    from services.shared.chart_render import render_chart_png, save_chart

    png_bytes = render_chart_png({
        "kind": "bar",
        "title": "Stay Liquid — Runway",
        "series": [{"name": "Runway months", "data": [138]}],
        "x_labels": ["May 2026"],
        "palette": "brooker",
    })
    # pass png_bytes directly to document.add_picture(io.BytesIO(png_bytes), ...)

Design choices:
- matplotlib Agg backend is set at import time (no display dependency).
- Brooker brand palette is the default.
- All I/O is synchronous — charts are fast (< 200 ms) and called from sync
  report-builder code, not from the async FastAPI event loop.
- Raises ValueError fast on bad input; never silently produces garbage charts.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Literal

# Set non-interactive backend BEFORE any other matplotlib import so it works
# in Docker containers without a display server.
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (must come after use("Agg"))
import matplotlib.patches as mpatches  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

from typing import TypedDict


class SeriesDict(TypedDict, total=False):
    name: str
    data: list[Any]
    labels: list[str]  # used by pie charts as slice labels


class AnnotationDict(TypedDict, total=False):
    x: str | int | float
    y: float
    text: str


class ChartSpec(TypedDict, total=False):
    kind: Literal["bar", "line", "pie", "stacked_bar", "horizontal_bar"]
    title: str
    x_label: str
    y_label: str
    series: list[SeriesDict]
    x_labels: list[str]
    annotations: list[AnnotationDict]
    palette: Literal["brooker", "muted", "default"]


# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

_PALETTES: dict[str, list[str]] = {
    "brooker": [
        "#0F3D5C",  # deep navy (primary)
        "#1F77B4",  # Brooker blue
        "#FF7F0E",  # amber
        "#2CA02C",  # green
        "#D62728",  # red
        "#9467BD",  # purple
    ],
    "muted": [
        "#6C757D",  # grey primary
        "#ADB5BD",  # light grey
        "#495057",  # dark grey
        "#1F77B4",  # single blue accent
        "#CED4DA",
        "#868E96",
    ],
    "default": [
        "#1F77B4",
        "#FF7F0E",
        "#2CA02C",
        "#D62728",
        "#9467BD",
        "#8C564B",
    ],
}

_DPI_DEFAULT = 160


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_chart_spec(spec: dict[str, Any]) -> ChartSpec:
    """Validate and normalise a raw dict into a ChartSpec.

    Required keys: ``kind``, ``series``.
    Performs numeric coercion on all series data values (float()).
    Raises ValueError with a descriptive message on any invalid input.
    """
    if not isinstance(spec, dict):
        raise ValueError(f"spec must be a dict, got {type(spec).__name__}")

    # --- required: kind ---
    if "kind" not in spec:
        raise ValueError("ChartSpec is missing required key: 'kind'")
    valid_kinds = {"bar", "line", "pie", "stacked_bar", "horizontal_bar"}
    kind = spec["kind"]
    if kind not in valid_kinds:
        raise ValueError(
            f"'kind' must be one of {sorted(valid_kinds)}, got {kind!r}"
        )

    # --- required: series ---
    if "series" not in spec:
        raise ValueError("ChartSpec is missing required key: 'series'")
    series = spec["series"]
    if not isinstance(series, list) or len(series) == 0:
        raise ValueError("'series' must be a non-empty list")

    # --- numeric coercion + length consistency ---
    x_labels: list[str] | None = spec.get("x_labels")
    normalised_series: list[SeriesDict] = []
    for i, s in enumerate(series):
        if not isinstance(s, dict):
            raise ValueError(f"series[{i}] must be a dict, got {type(s).__name__}")
        if "data" not in s:
            raise ValueError(f"series[{i}] is missing required key: 'data'")
        raw_data = s["data"]
        if not isinstance(raw_data, list):
            raise ValueError(f"series[{i}]['data'] must be a list")

        # coerce every value to float
        coerced: list[float] = []
        for j, v in enumerate(raw_data):
            try:
                coerced.append(float(v))  # type: ignore[arg-type]
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"series[{i}]['data'][{j}] cannot be coerced to float: {v!r}"
                ) from exc

        # length must match x_labels when provided (pie ignores x_labels)
        if x_labels is not None and kind != "pie" and len(coerced) != len(x_labels):
            raise ValueError(
                f"series[{i}]['data'] has {len(coerced)} items but "
                f"x_labels has {len(x_labels)} items — they must match"
            )

        entry: SeriesDict = {"name": s.get("name", f"Series {i+1}"), "data": coerced}
        if "labels" in s:
            entry["labels"] = [str(lbl) for lbl in s["labels"]]
        normalised_series.append(entry)

    # --- palette ---
    palette = spec.get("palette", "brooker")
    if palette not in _PALETTES:
        raise ValueError(
            f"'palette' must be one of {sorted(_PALETTES.keys())}, got {palette!r}"
        )

    result: ChartSpec = {
        "kind": kind,  # type: ignore[typeddict-item]
        "series": normalised_series,
        "palette": palette,  # type: ignore[typeddict-item]
    }
    for optional in ("title", "x_label", "y_label", "x_labels", "annotations"):
        if optional in spec:
            result[optional] = spec[optional]  # type: ignore[literal-required]

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_palette(spec: ChartSpec) -> list[str]:
    return _PALETTES.get(spec.get("palette", "brooker"), _PALETTES["brooker"])


def _apply_base_style(fig: plt.Figure, ax: Axes, spec: ChartSpec, gridlines: bool = True) -> None:
    """Apply consistent Brooker visual style to an axes object."""
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    title = spec.get("title", "")
    if title:
        ax.set_title(title, fontsize=16, fontweight="bold", pad=12)

    x_label = spec.get("x_label", "")
    if x_label:
        ax.set_xlabel(x_label, fontsize=12)

    y_label = spec.get("y_label", "")
    if y_label:
        ax.set_ylabel(y_label, fontsize=12)

    ax.tick_params(axis="both", labelsize=10)

    # Remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if gridlines:
        ax.yaxis.grid(True, linestyle="--", alpha=0.5, color="#CCCCCC", zorder=0)
        ax.set_axisbelow(True)


def _add_annotations(ax: Axes, spec: ChartSpec, x_labels: list[str] | None) -> None:
    """Render small grey arrows + text for each annotation in the spec."""
    annotations = spec.get("annotations", [])
    if not annotations:
        return

    for ann in annotations:
        x_val = ann.get("x")
        y_val = ann.get("y")
        text = ann.get("text", "")
        if x_val is None or y_val is None:
            continue

        # Resolve string x values to numeric positions
        x_pos: float
        if isinstance(x_val, str) and x_labels and x_val in x_labels:
            x_pos = float(x_labels.index(x_val))
        else:
            try:
                x_pos = float(x_val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue

        ax.annotate(
            text,
            xy=(x_pos, float(y_val)),
            xytext=(x_pos + 0.3, float(y_val) * 1.05),
            fontsize=9,
            color="#555555",
            arrowprops=dict(arrowstyle="->", color="#888888", lw=0.8),
        )


def _fig_to_png(fig: plt.Figure, dpi: int) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Chart renderers (one per kind)
# ---------------------------------------------------------------------------

def _render_bar(spec: ChartSpec, width_px: int, height_px: int, dpi: int) -> bytes:
    colours = _get_palette(spec)
    series = spec["series"]
    x_labels = spec.get("x_labels", [str(i) for i in range(len(series[0]["data"]))])
    n_groups = len(x_labels)
    n_series = len(series)
    bar_width = 0.8 / n_series
    x_indices = list(range(n_groups))

    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi))
    _apply_base_style(fig, ax, spec, gridlines=True)

    for i, s in enumerate(series):
        offsets = [x + (i - n_series / 2 + 0.5) * bar_width for x in x_indices]
        colour = colours[i % len(colours)]
        ax.bar(offsets, s["data"], width=bar_width, label=s.get("name", ""),
               color=colour, zorder=3)

    ax.set_xticks(x_indices)
    ax.set_xticklabels(x_labels, fontsize=10)

    _add_annotations(ax, spec, x_labels)

    if n_series > 1:
        ax.legend(fontsize=10)

    fig.tight_layout()
    return _fig_to_png(fig, dpi)


def _render_stacked_bar(spec: ChartSpec, width_px: int, height_px: int, dpi: int) -> bytes:
    colours = _get_palette(spec)
    series = spec["series"]
    x_labels = spec.get("x_labels", [str(i) for i in range(len(series[0]["data"]))])
    n_groups = len(x_labels)
    x_indices = list(range(n_groups))

    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi))
    _apply_base_style(fig, ax, spec, gridlines=True)

    bottoms = [0.0] * n_groups
    for i, s in enumerate(series):
        colour = colours[i % len(colours)]
        ax.bar(x_indices, s["data"], bottom=bottoms, label=s.get("name", ""),
               color=colour, zorder=3)
        bottoms = [b + v for b, v in zip(bottoms, s["data"])]

    ax.set_xticks(x_indices)
    ax.set_xticklabels(x_labels, fontsize=10)

    _add_annotations(ax, spec, x_labels)

    if len(series) > 1:
        ax.legend(fontsize=10)

    fig.tight_layout()
    return _fig_to_png(fig, dpi)


def _render_horizontal_bar(spec: ChartSpec, width_px: int, height_px: int, dpi: int) -> bytes:
    colours = _get_palette(spec)
    series = spec["series"]
    x_labels = spec.get("x_labels", [str(i) for i in range(len(series[0]["data"]))])
    n_groups = len(x_labels)
    n_series = len(series)
    bar_height = 0.8 / n_series
    y_indices = list(range(n_groups))

    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi))

    # Horizontal bars: gridlines on x-axis, not y
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    title = spec.get("title", "")
    if title:
        ax.set_title(title, fontsize=16, fontweight="bold", pad=12)
    x_label = spec.get("x_label", "")
    if x_label:
        ax.set_xlabel(x_label, fontsize=12)
    y_label = spec.get("y_label", "")
    if y_label:
        ax.set_ylabel(y_label, fontsize=12)
    ax.tick_params(axis="both", labelsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, color="#CCCCCC", zorder=0)
    ax.set_axisbelow(True)

    for i, s in enumerate(series):
        offsets = [y + (i - n_series / 2 + 0.5) * bar_height for y in y_indices]
        colour = colours[i % len(colours)]
        ax.barh(offsets, s["data"], height=bar_height, label=s.get("name", ""),
                color=colour, zorder=3)

    ax.set_yticks(y_indices)
    ax.set_yticklabels(x_labels, fontsize=10)

    if n_series > 1:
        ax.legend(fontsize=10)

    fig.tight_layout()
    return _fig_to_png(fig, dpi)


def _render_line(spec: ChartSpec, width_px: int, height_px: int, dpi: int) -> bytes:
    colours = _get_palette(spec)
    series = spec["series"]
    x_labels = spec.get("x_labels", [str(i) for i in range(len(series[0]["data"]))])
    x_indices = list(range(len(x_labels)))

    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi))
    _apply_base_style(fig, ax, spec, gridlines=True)

    for i, s in enumerate(series):
        colour = colours[i % len(colours)]
        ax.plot(x_indices, s["data"], marker="o", label=s.get("name", ""),
                color=colour, linewidth=2, markersize=5, zorder=3)

    ax.set_xticks(x_indices)
    ax.set_xticklabels(x_labels, fontsize=10)

    _add_annotations(ax, spec, x_labels)

    if len(series) > 1:
        ax.legend(fontsize=10)

    fig.tight_layout()
    return _fig_to_png(fig, dpi)


def _render_pie(spec: ChartSpec, width_px: int, height_px: int, dpi: int) -> bytes:
    colours = _get_palette(spec)
    series_0 = spec["series"][0]
    data = series_0["data"]

    # Labels: prefer series[0]["labels"], fall back to x_labels, then generic
    if "labels" in series_0 and series_0["labels"]:
        labels = series_0["labels"]
    elif spec.get("x_labels"):
        labels = spec["x_labels"]
    else:
        labels = [f"Slice {i+1}" for i in range(len(data))]

    # Ensure colours list is long enough
    pie_colours = (colours * ((len(data) // len(colours)) + 1))[:len(data)]

    fig, ax = plt.subplots(figsize=(width_px / dpi, height_px / dpi))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    title = spec.get("title", "")
    if title:
        ax.set_title(title, fontsize=16, fontweight="bold", pad=12)

    wedges, texts, autotexts = ax.pie(
        data,
        labels=labels,
        colors=pie_colours,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.82,
    )
    for t in texts:
        t.set_fontsize(10)
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")

    ax.axis("equal")
    fig.tight_layout()
    return _fig_to_png(fig, dpi)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_RENDERERS = {
    "bar": _render_bar,
    "stacked_bar": _render_stacked_bar,
    "horizontal_bar": _render_horizontal_bar,
    "line": _render_line,
    "pie": _render_pie,
}

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def render_chart_png(
    spec: ChartSpec,
    *,
    width_px: int = 1280,
    height_px: int = 720,
    dpi: int = 160,
) -> bytes:
    """Render the chart spec to a PNG and return raw bytes.

    Uses matplotlib with the Agg backend (headless — no display required).
    Validates and normalises the spec before rendering.

    Args:
        spec: ChartSpec dict describing the chart.
        width_px: Output width in pixels (default 1280).
        height_px: Output height in pixels (default 720).
        dpi: Dots-per-inch for the rasteriser (default 160).

    Returns:
        Raw PNG bytes starting with the PNG magic bytes ``\\x89PNG\\r\\n\\x1a\\n``.

    Raises:
        ValueError: If the spec is invalid (missing required keys, type mismatches,
                    series/x_labels length mismatch, un-coercible numeric strings).
    """
    validated = validate_chart_spec(dict(spec))
    kind: str = validated["kind"]  # type: ignore[typeddict-item]
    renderer = _RENDERERS[kind]
    png_bytes = renderer(validated, width_px, height_px, dpi)
    assert png_bytes[:8] == _PNG_MAGIC, "matplotlib produced non-PNG output"
    return png_bytes


def save_chart(
    spec: ChartSpec,
    out_path: str | Path,
    **kwargs: Any,
) -> Path:
    """Render and write a PNG to ``out_path``. Returns the resolved Path.

    All keyword arguments are forwarded to ``render_chart_png``.
    Creates parent directories as needed.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    png_bytes = render_chart_png(spec, **kwargs)
    out.write_bytes(png_bytes)
    return out
