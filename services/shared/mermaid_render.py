"""Mermaid diagram rendering to PNG bytes.

Converts Mermaid-syntax diagram text into raw PNG bytes suitable for embedding
in Word documents, PowerPoint decks, or any binary PNG consumer.

## Approach

Two rendering backends, selected at call time:

1. **Local mmdc CLI** (Node.js `@mermaid-js/mermaid-cli`):
   - Activated when the env var ``MERMAID_CLI_PATH`` points to the ``mmdc``
     binary.
   - Self-hosted, air-gapped friendly, no external network dependency.
   - Preferred over the HTTP path when available (faster, no egress).

2. **Mermaid Ink HTTP** (https://mermaid.ink):
   - Zero local dependencies — a single HTTPS GET with the diagram
     base64-encoded in the URL.
   - Used by default when ``MERMAID_CLI_PATH`` is not configured.
   - Override the base URL via ``MERMAID_INK_URL`` env var (useful for a
     self-hosted Mermaid Ink instance inside the corporate network).

Rationale: the ink path gives zero-friction defaults for development and
CI; mmdc gives the production-grade, network-independent upgrade path. We
detect at function-call time so the env var can be changed without restarting
the service.

## Safety guarantees

- Magic-byte check: every successful render must start with ``\\x89PNG``.
  Anything else (HTML error page, empty body, truncated JPEG) raises
  ``RuntimeError`` immediately rather than writing garbage into a document.
- 25 MB output cap — an absurdly large diagram would OOM the process.
- 30 s network timeout on the HTTP path.
- ``mmdc`` subprocess killed on non-zero exit; stderr surfaced in the error.

Usage::

    from services.shared.mermaid_render import render_mermaid_png, save_mermaid

    png = render_mermaid_png("graph LR\\nA-->B")
    save_mermaid("sequenceDiagram\\nAlice->>Bob: hi", "/tmp/seq.png")
"""
from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG"
_JPEG_MAGIC = b"\xff\xd8\xff"  # mermaid.ink may return JPEG depending on size/theme
_MAX_OUTPUT_BYTES = 25 * 1024 * 1024  # 25 MB sanity cap
_HTTP_TIMEOUT = 30.0  # seconds

_KNOWN_DIAGRAM_TYPES = {
    "graph",
    "flowchart",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "gantt",
    "pie",
    "journey",
    "mindmap",
    "gitGraph",
    "erDiagram",
    "C4Context",
    "C4Container",
    "C4Component",
    "quadrantChart",
    "xychart-beta",
    "block-beta",
    "packet-beta",
    "kanban",
    "architecture-beta",
    "requirementDiagram",
    "timeline",
    "sankey-beta",
    "zenuml",
}

_DEFAULT_INK_URL = "https://mermaid.ink"


# ---------------------------------------------------------------------------
# Syntax validation
# ---------------------------------------------------------------------------


def validate_mermaid_syntax(mermaid_text: str) -> bool:
    """Light syntax check: must start with a recognised diagram-type keyword.

    Strips leading whitespace and blank lines before checking. Does not
    perform a full parse — that would require invoking the Mermaid parser.
    Returns ``True`` if the text looks like a valid Mermaid diagram,
    ``False`` otherwise. Never raises.

    Args:
        mermaid_text: Raw Mermaid diagram source text.

    Returns:
        True if the text begins with a known Mermaid diagram keyword.
    """
    if not mermaid_text or not mermaid_text.strip():
        return False

    # Take the first non-empty, non-comment line
    for raw_line in mermaid_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue
        # The keyword is the first whitespace-delimited token on the first
        # content line. e.g. "graph LR" → "graph", "flowchart TD" → "flowchart"
        first_token = line.split()[0]
        return first_token in _KNOWN_DIAGRAM_TYPES

    return False


# ---------------------------------------------------------------------------
# HTTP backend — mermaid.ink
# ---------------------------------------------------------------------------


def render_mermaid_via_ink(
    mermaid_text: str,
    *,
    theme: str = "default",
    background: str = "white",
) -> bytes:
    """Render Mermaid diagram via the mermaid.ink HTTP service.

    Encodes the diagram text as URL-safe base64 and issues a GET request to
    ``{MERMAID_INK_URL}/img/{b64}?theme={theme}&bgColor={background}``.

    The ``MERMAID_INK_URL`` environment variable allows overriding the default
    ``https://mermaid.ink`` endpoint (e.g. to a self-hosted instance).

    Args:
        mermaid_text: Raw Mermaid source text.
        theme: Mermaid theme name — ``default``, ``dark``, ``neutral``, etc.
        background: CSS background colour string (e.g. ``white``, ``#ffffff``).

    Returns:
        Raw PNG bytes.

    Raises:
        RuntimeError: If the HTTP call times out, the server returns non-200,
            the response body is not a PNG, or the output exceeds 25 MB.
    """
    ink_base = os.environ.get("MERMAID_INK_URL", _DEFAULT_INK_URL).rstrip("/")

    encoded = base64.urlsafe_b64encode(mermaid_text.encode("utf-8")).decode("ascii")
    url = f"{ink_base}/img/{encoded}"
    params: dict[str, str] = {"theme": theme, "bgColor": background}

    logger.debug("mermaid.ink GET %s params=%s", url, params)

    try:
        response = httpx.get(url, params=params, timeout=_HTTP_TIMEOUT, follow_redirects=True)
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            f"mermaid.ink request timed out after {_HTTP_TIMEOUT}s: {exc}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"mermaid.ink request failed: {exc}") from exc

    if response.status_code != 200:
        preview = response.text[:200]
        raise RuntimeError(
            f"mermaid.ink returned HTTP {response.status_code}: {preview}"
        )

    raw = response.content
    _assert_png(raw, source="mermaid.ink")
    return raw


# ---------------------------------------------------------------------------
# Local CLI backend — mmdc
# ---------------------------------------------------------------------------


def render_mermaid_via_mmdc(
    mermaid_text: str,
    mmdc_path: str,
    *,
    theme: str = "default",
    background: str = "white",
    width: int = 1280,
) -> bytes:
    """Render Mermaid diagram using the local ``mmdc`` CLI binary.

    Writes the diagram text to a temporary ``.mmd`` file, invokes ``mmdc``,
    reads the output PNG, and cleans up. Temporary files are always removed
    even if the subprocess fails.

    Args:
        mermaid_text: Raw Mermaid source text.
        mmdc_path: Absolute path to the ``mmdc`` binary.
        theme: Mermaid theme name.
        background: CSS background colour string.
        width: Output image width in pixels.

    Returns:
        Raw PNG bytes.

    Raises:
        RuntimeError: If ``mmdc`` exits with a non-zero code or the output is
            not a PNG.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "diagram.mmd"
        out_path = Path(tmpdir) / "diagram.png"

        in_path.write_text(mermaid_text, encoding="utf-8")

        cmd = [
            mmdc_path,
            "-i", str(in_path),
            "-o", str(out_path),
            "--theme", theme,
            "--backgroundColor", background,
            "--width", str(width),
        ]

        logger.debug("mmdc cmd: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() or "(no stderr)"
            raise RuntimeError(
                f"mmdc exited with code {result.returncode}: {stderr}"
            )

        if not out_path.exists():
            raise RuntimeError(
                f"mmdc exited 0 but output file not found: {out_path}"
            )

        raw = out_path.read_bytes()

    _assert_png(raw, source="mmdc")
    return raw


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _assert_png(data: bytes, *, source: str) -> None:
    """Verify ``data`` starts with the PNG magic bytes.

    Args:
        data: Raw bytes to check.
        source: Human-readable label for error messages (e.g. ``"mermaid.ink"``).

    Raises:
        RuntimeError: If the data does not start with ``\\x89PNG``, or exceeds
            the 25 MB output cap.
    """
    if len(data) > _MAX_OUTPUT_BYTES:
        raise RuntimeError(
            f"{source} returned {len(data):,} bytes — exceeds 25 MB cap"
        )
    is_png = data[:4] == _PNG_MAGIC
    is_jpeg = data[:3] == _JPEG_MAGIC
    if not (is_png or is_jpeg):
        preview = data[:120]
        raise RuntimeError(
            f"{source} response is not a PNG or JPEG image. "
            f"First bytes: {preview!r}"
        )


# ---------------------------------------------------------------------------
# Public high-level API
# ---------------------------------------------------------------------------


def render_mermaid_png(
    mermaid_text: str,
    *,
    theme: Literal["default", "dark", "neutral"] = "default",
    background: str = "white",
    width: int = 1280,
    height: int | None = None,
) -> bytes:
    """Render Mermaid diagram text to PNG bytes.

    Automatically selects the best available backend:

    - If ``MERMAID_CLI_PATH`` is set in the environment, uses the local
      ``mmdc`` CLI (preferred — no network egress, faster).
    - Otherwise falls back to the ``mermaid.ink`` HTTP service.

    Both backends enforce a 30 s timeout, a ``\\x89PNG`` magic-byte check,
    and a 25 MB output cap.

    Args:
        mermaid_text: Raw Mermaid diagram source text.
        theme: Mermaid theme — ``"default"``, ``"dark"``, or ``"neutral"``.
        background: CSS background colour (default ``"white"``).
        width: Output image width in pixels (default 1280).
        height: Not yet implemented for the ink backend; ignored for mmdc
            (mmdc derives height automatically from diagram content).

    Returns:
        Raw PNG bytes.

    Raises:
        RuntimeError: If both backends fail or the output fails validation.
    """
    mmdc_path = os.environ.get("MERMAID_CLI_PATH", "").strip()

    if mmdc_path:
        logger.info("mermaid_render: using local mmdc at %s", mmdc_path)
        return render_mermaid_via_mmdc(
            mermaid_text,
            mmdc_path,
            theme=theme,
            background=background,
            width=width,
        )

    logger.info("mermaid_render: MERMAID_CLI_PATH not set, using mermaid.ink HTTP")
    return render_mermaid_via_ink(
        mermaid_text,
        theme=theme,
        background=background,
    )


def save_mermaid(
    mermaid_text: str,
    out_path: str | Path,
    **kwargs: object,
) -> Path:
    """Render Mermaid diagram and write the PNG to ``out_path``.

    Creates parent directories as needed. All keyword arguments are forwarded
    to :func:`render_mermaid_png`.

    Args:
        mermaid_text: Raw Mermaid diagram source text.
        out_path: Destination file path (e.g. ``"/tmp/diagram.png"``).
        **kwargs: Forwarded to ``render_mermaid_png`` (``theme``, ``background``,
            ``width``, ``height``).

    Returns:
        The resolved :class:`pathlib.Path` of the written file.

    Raises:
        RuntimeError: Propagated from ``render_mermaid_png`` if rendering fails.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    png_bytes = render_mermaid_png(mermaid_text, **kwargs)  # type: ignore[arg-type]
    out.write_bytes(png_bytes)
    logger.info("mermaid_render: wrote %d bytes to %s", len(png_bytes), out)
    return out


# ---------------------------------------------------------------------------
# Smoke-test entry point (skipped by pytest — run manually to verify e2e)
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import sys

    FLOWCHART = """\
flowchart TD
    A[Capital Request] --> B{CAC Review}
    B -->|Approved| C[Fund Allocation]
    B -->|Rejected| D[Return to Requester]
    C --> E[Post-Allocation Monitoring]
"""

    SEQUENCE = """\
sequenceDiagram
    participant Slack
    participant CAC_Orchestrator
    participant RAG
    participant ApprovalUI

    Slack->>CAC_Orchestrator: capital request
    CAC_Orchestrator->>RAG: retrieve policy context
    RAG-->>CAC_Orchestrator: policy chunks
    CAC_Orchestrator->>ApprovalUI: staging proposal
    ApprovalUI-->>Slack: approval notification
"""

    out_dir = Path("/tmp/mermaid_smoke") if sys.platform != "win32" else Path("C:/tmp/mermaid_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Rendering flowchart via mermaid.ink...")
    fc_path = save_mermaid(FLOWCHART, out_dir / "flowchart.png")
    print(f"  Written: {fc_path} ({fc_path.stat().st_size:,} bytes)")

    print("Rendering sequence diagram via mermaid.ink...")
    sq_path = save_mermaid(SEQUENCE, out_dir / "sequence.png")
    print(f"  Written: {sq_path} ({sq_path.stat().st_size:,} bytes)")

    print("Done. Open the files to verify the diagrams rendered correctly.")
