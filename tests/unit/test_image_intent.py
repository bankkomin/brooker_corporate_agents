"""Unit tests for services/slack-bot/src/image_intent.py.

All LLM calls are mocked — no vLLM, no network, no MinIO.

Run with:
    python -m pytest tests/unit/test_image_intent.py -v
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path fixup so imports resolve without installing the package
# ---------------------------------------------------------------------------
import sys

_SRC = Path(__file__).parents[2] / "services" / "slack-bot" / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from image_intent import (  # noqa: E402
    ImagePlacementSpec,
    ImageUploadInfo,
    _build_extraction_prompt,
    _default_placement,
    _parse_llm_response,
    extract_image_placement,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_upload(n: int = 1) -> list[ImageUploadInfo]:
    """Return n minimal ImageUploadInfo dicts."""
    return [
        ImageUploadInfo(
            minio_key=f"uploads/file{i}.png",
            filename=f"file{i}.png",
            file_id=f"F00{i}",
            channel_id="C001",
        )
        for i in range(1, n + 1)
    ]


def _fenced(payload: Any) -> str:
    """Wrap a Python object as a ```json fenced block."""
    return f"```json\n{json.dumps(payload)}\n```"


def _make_mock_llm(raw_response: str) -> MagicMock:
    """Return a mock LLM client whose ainvoke returns *raw_response* as .content."""
    response = MagicMock()
    response.content = raw_response
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=response)
    return llm


# ---------------------------------------------------------------------------
# _default_placement
# ---------------------------------------------------------------------------


def test_default_placement_when_no_message_text():
    """Empty message → all hints null, caption = filename stem, width_inches = 5.5."""
    uploads = _make_upload(2)
    specs = _default_placement(uploads, "deck")

    assert len(specs) == 2
    # All placement hints must be null / absent
    for spec, upload in zip(specs, uploads):
        assert spec["minio_key"] == upload["minio_key"]
        assert spec["slide_index"] is None
        assert spec["slide_title_hint"] is None
        assert spec["caption"] == Path(upload["filename"]).stem
        assert spec["width_inches"] == 5.5


def test_default_placement_report_kind():
    """Report kind → section_hint=None, no slide_ keys."""
    uploads = _make_upload(1)
    specs = _default_placement(uploads, "report")

    assert specs[0]["section_hint"] is None
    assert "slide_index" not in specs[0]
    assert "slide_title_hint" not in specs[0]


def test_default_placement_when_no_uploads():
    """Empty uploads → empty result list."""
    assert _default_placement([], "deck") == []


# ---------------------------------------------------------------------------
# _parse_llm_response — fenced JSON
# ---------------------------------------------------------------------------


def test_parse_llm_response_extracts_fenced_json():
    """```json``` fenced block parses correctly for deck kind."""
    uploads = _make_upload(2)
    payload = [
        {"slide_index": 0, "slide_title_hint": None, "caption": None},
        {"slide_index": 2, "slide_title_hint": "Financials", "caption": "Q1"},
    ]
    raw = _fenced(payload)

    specs = _parse_llm_response(raw, uploads, "deck")

    assert len(specs) == 2
    assert specs[0]["slide_index"] == 0
    assert specs[0]["caption"] is None
    assert specs[1]["slide_index"] == 2
    assert specs[1]["slide_title_hint"] == "Financials"
    assert specs[1]["caption"] == "Q1"
    # minio_keys must be copied through
    assert specs[0]["minio_key"] == uploads[0]["minio_key"]
    assert specs[1]["minio_key"] == uploads[1]["minio_key"]


# ---------------------------------------------------------------------------
# _parse_llm_response — bare JSON
# ---------------------------------------------------------------------------


def test_parse_llm_response_extracts_bare_json():
    """Raw JSON array (no fences) also parses correctly."""
    uploads = _make_upload(1)
    payload = [{"slide_index": 1, "slide_title_hint": None, "caption": "Intro"}]
    raw = json.dumps(payload)

    specs = _parse_llm_response(raw, uploads, "deck")

    assert len(specs) == 1
    assert specs[0]["slide_index"] == 1
    assert specs[0]["caption"] == "Intro"


# ---------------------------------------------------------------------------
# _parse_llm_response — fallback paths
# ---------------------------------------------------------------------------


def test_parse_llm_response_falls_back_on_invalid_json():
    """Completely unparseable garbage → default placement, no exception."""
    uploads = _make_upload(2)
    raw = "This is definitely not JSON at all! @@##$$"

    specs = _parse_llm_response(raw, uploads, "deck")

    # Must return a spec for every upload (default placement)
    assert len(specs) == len(uploads)
    for spec, upload in zip(specs, uploads):
        assert spec["minio_key"] == upload["minio_key"]
        assert spec["slide_index"] is None


def test_parse_llm_response_falls_back_on_length_mismatch():
    """LLM returns 1 entry for 2 uploads → fall back to default placement."""
    uploads = _make_upload(2)
    payload = [{"slide_index": 0, "slide_title_hint": None, "caption": None}]
    raw = _fenced(payload)

    specs = _parse_llm_response(raw, uploads, "deck")

    # Must return 2 specs (one per upload), all default
    assert len(specs) == 2
    for spec in specs:
        assert spec["slide_index"] is None


# ---------------------------------------------------------------------------
# extract_image_placement — async integration through mocked LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_returns_one_spec_per_upload_in_order():
    """3 uploads → 3 specs with minio_keys in the same order."""
    uploads = _make_upload(3)
    payload = [
        {"slide_index": 0, "slide_title_hint": None, "caption": None},
        {"slide_index": 1, "slide_title_hint": None, "caption": None},
        {"slide_index": 2, "slide_title_hint": None, "caption": None},
    ]
    llm = _make_mock_llm(_fenced(payload))

    specs = await extract_image_placement(
        "put image 1 on slide 1, image 2 on slide 2, image 3 on slide 3",
        uploads,
        llm_client=llm,
    )

    assert len(specs) == 3
    for i, (spec, upload) in enumerate(zip(specs, uploads)):
        assert spec["minio_key"] == upload["minio_key"], (
            f"minio_key mismatch at index {i}"
        )


@pytest.mark.asyncio
async def test_extract_caption_for_deck_kind():
    """Mocked LLM returns caption 'Q1 results' → flows through unchanged."""
    uploads = _make_upload(1)
    payload = [{"slide_index": 3, "slide_title_hint": None, "caption": "Q1 results"}]
    llm = _make_mock_llm(_fenced(payload))

    specs = await extract_image_placement(
        "use this chart on slide 4 with caption Q1 results",
        uploads,
        llm_client=llm,
        artefact_kind="deck",
    )

    assert specs[0]["caption"] == "Q1 results"


@pytest.mark.asyncio
async def test_extract_slide_index_for_deck_kind():
    """Mocked LLM returns slide_index=2 → spec carries slide_index=2."""
    uploads = _make_upload(1)
    payload = [{"slide_index": 2, "slide_title_hint": None, "caption": None}]
    llm = _make_mock_llm(_fenced(payload))

    specs = await extract_image_placement(
        "put this on slide 3",
        uploads,
        llm_client=llm,
        artefact_kind="deck",
    )

    assert specs[0]["slide_index"] == 2


@pytest.mark.asyncio
async def test_extract_section_hint_for_report_kind():
    """Report kind: mocked LLM returns section_hint 'Executive Summary'."""
    uploads = _make_upload(1)
    payload = [{"section_hint": "Executive Summary", "caption": "Overview"}]
    llm = _make_mock_llm(_fenced(payload))

    specs = await extract_image_placement(
        "put this in the Executive Summary section",
        uploads,
        llm_client=llm,
        artefact_kind="report",
    )

    assert specs[0]["section_hint"] == "Executive Summary"
    assert specs[0]["caption"] == "Overview"
    # deck keys must NOT be present
    assert "slide_index" not in specs[0]
    assert "slide_title_hint" not in specs[0]


# ---------------------------------------------------------------------------
# extract_image_placement — edge / fallback cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_empty_message_falls_back_without_hitting_llm():
    """Blank message_text → default placement, LLM is never called."""
    uploads = _make_upload(2)
    llm = _make_mock_llm("should not be called")

    specs = await extract_image_placement("", uploads, llm_client=llm)

    llm.ainvoke.assert_not_called()
    assert len(specs) == 2
    for spec in specs:
        assert spec["slide_index"] is None


@pytest.mark.asyncio
async def test_extract_no_uploads_returns_empty():
    """No uploads → empty list, LLM is never called."""
    llm = _make_mock_llm("should not be called")

    specs = await extract_image_placement("put logo on title slide", [], llm_client=llm)

    llm.ainvoke.assert_not_called()
    assert specs == []


@pytest.mark.asyncio
async def test_extract_llm_exception_falls_back_to_default():
    """LLM raises an exception → default placement, no propagation."""
    uploads = _make_upload(2)
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("vLLM unavailable"))

    specs = await extract_image_placement("put the chart on slide 2", uploads, llm_client=llm)

    assert len(specs) == 2
    for spec in specs:
        assert spec["slide_index"] is None


# ---------------------------------------------------------------------------
# test_extract_uses_temperature_zero
# ---------------------------------------------------------------------------


def test_extract_uses_temperature_zero():
    """Default LLM client is constructed with temperature=0.0.

    We patch the module-level ChatOpenAI name in image_intent (where it was
    imported at load time) so the factory call resolves to our mock.
    """
    with patch("image_intent.ChatOpenAI") as MockChat:
        MockChat.return_value = MagicMock()
        with patch.dict("os.environ", {
            "VLLM_LARGE_URL": "http://host.docker.internal:8000/v1",
            "VLLM_LARGE_MODEL": "qwen-large",
        }):
            from image_intent import _make_default_llm_client
            _make_default_llm_client()

    assert MockChat.called, "ChatOpenAI constructor was never called"
    _, kwargs = MockChat.call_args
    assert kwargs.get("temperature") == 0.0, (
        f"Expected temperature=0.0, got {kwargs.get('temperature')!r}"
    )


# ---------------------------------------------------------------------------
# _build_extraction_prompt (sanity check)
# ---------------------------------------------------------------------------


def test_build_extraction_prompt_includes_all_filenames():
    """User prompt contains every filename in numbered order."""
    uploads = _make_upload(3)
    prompt = _build_extraction_prompt("some message", uploads, "deck")

    for i, upload in enumerate(uploads, start=1):
        assert f"{i}. {upload['filename']}" in prompt


def test_build_extraction_prompt_handles_empty_message():
    """Empty message_text is represented as a placeholder, not a crash."""
    uploads = _make_upload(1)
    prompt = _build_extraction_prompt("", uploads, "deck")

    assert "1. file1.png" in prompt
    # Should not raise and should contain some message placeholder
    assert "Message:" in prompt
