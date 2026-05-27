"""Parse natural-language image placement instructions from Slack messages.

Given a message like "put the logo on the title slide and use this chart on
slide 3 with caption Q1 results", return a structured list mapping each
uploaded image filename → slide placement + caption.

Public API
----------
    extract_image_placement(message_text, image_uploads, ...)
        -> list[ImagePlacementSpec]

Fallback contract
-----------------
Returns one ImagePlacementSpec per input upload (order preserved) with all
hints set to None whenever:
  - image_uploads is empty   → returns []
  - message_text is blank    → all hints null, caption = filename stem
  - LLM returns invalid JSON → all hints null, caption = filename stem
  - LLM array length mismatch → same
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import PurePosixPath
from typing import TypedDict

import structlog

logger = structlog.get_logger("slack-bot.image_intent")

# ---------------------------------------------------------------------------
# Optional heavy deps — imported at module load so they can be patched in tests
# ---------------------------------------------------------------------------

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore[assignment,misc]

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:  # pragma: no cover
    HumanMessage = None  # type: ignore[assignment,misc]
    SystemMessage = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Public TypedDicts
# ---------------------------------------------------------------------------


class ImageUploadInfo(TypedDict):
    minio_key: str
    filename: str
    file_id: str
    channel_id: str  # not required by extractor but useful context


class ImagePlacementSpec(TypedDict, total=False):
    minio_key: str            # required — copied through from input
    section_hint: str | None  # for docx — heading substring match
    slide_index: int | None   # for pptx — 0-based
    slide_title_hint: str | None
    caption: str | None
    width_inches: float       # default 5.5


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = (
    "You map uploaded images to placement instructions for a {{artefact_kind}}.\n"
    "Given a user message and a list of image filenames, return a JSON array\n"
    "where each element corresponds to one uploaded image (in input order).\n"
    "\n"
    "For a deck (pptx), each element MUST have:\n"
    '  - "slide_index": integer (0-based) OR null\n'
    '  - "slide_title_hint": case-insensitive substring of a slide title OR null\n'
    '  - "caption": short text shown under the image OR null\n'
    "\n"
    "For a report (docx), each element MUST have:\n"
    '  - "section_hint": case-insensitive substring of a heading OR null\n'
    '  - "caption": short text below the image OR null\n'
    "\n"
    "Rules:\n"
    "  - Output VALID JSON only, fenced in ```json ... ``` block.\n"
    "  - Array length MUST equal the number of uploads provided.\n"
    "  - If the message doesn't mention an image, set all hints to null\n"
    "    (the renderer will append it at the end).\n"
    '  - Slide indices are 0-based. "Title slide" = 0. "Slide 3" = 2.\n'
    "  - Caption: extract the verbatim phrase, do not paraphrase.\n"
    '  - Filenames are hints — match phrases like "logo" to "company_logo.png".\n'
    "\n"
    "Example input:\n"
    "  Message: \"put the logo on the title slide, and the runway chart on slide 4 as 'Stay Liquid'\"\n"
    '  Uploads: [{{"filename": "company_logo.png"}}, {{"filename": "runway_chart.png"}}]\n'
    "\n"
    "Example output:\n"
    "```json\n"
    "[\n"
    '  {{"slide_index": 0, "slide_title_hint": null, "caption": null}},\n'
    '  {{"slide_index": 3, "slide_title_hint": null, "caption": "Stay Liquid"}}\n'
    "]\n"
    "```"
)

_USER_PROMPT_TEMPLATE = (
    "Message: {message_text}\n"
    "\n"
    "Uploads (in order):\n"
    "{upload_list}\n"
    "\n"
    "Return the JSON now."
)

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_extraction_prompt(
    message_text: str,
    uploads: list[ImageUploadInfo],
    artefact_kind: str,
) -> str:
    """Compose the user prompt for the LLM."""
    lines = [f"{i + 1}. {u['filename']}" for i, u in enumerate(uploads)]
    return _USER_PROMPT_TEMPLATE.format(
        message_text=message_text or "(no message)",
        upload_list="\n".join(lines),
    )


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

_FENCED_JSON_RE = re.compile(
    r"```(?:json)?\s*([\s\S]*?)```",
    re.IGNORECASE,
)


def _extract_json_array(text: str) -> list | None:
    """Find a JSON array in *text*.

    Tries fenced ```json ... ``` blocks first, then bare json.loads of the
    stripped text.  Returns None if nothing parses.
    """
    # 1. Fenced block
    m = _FENCED_JSON_RE.search(text)
    if m:
        candidate = m.group(1).strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # 2. Bare JSON — find the first '[' and attempt to parse from there
    stripped = text.strip()
    start = stripped.find("[")
    if start != -1:
        try:
            parsed = json.loads(stripped[start:])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Placement spec assembly
# ---------------------------------------------------------------------------

_DEFAULT_WIDTH: float = 5.5


def _spec_from_llm_item(
    item: dict,
    upload: ImageUploadInfo,
    artefact_kind: str,
) -> ImagePlacementSpec:
    """Convert one LLM-returned dict + the matching upload into an ImagePlacementSpec."""
    spec: ImagePlacementSpec = {
        "minio_key": upload["minio_key"],
        "width_inches": _DEFAULT_WIDTH,
        "caption": item.get("caption") or None,
    }

    if artefact_kind == "report":
        spec["section_hint"] = item.get("section_hint") or None
    else:
        # deck (pptx) — and anything else we don't recognise
        raw_idx = item.get("slide_index")
        spec["slide_index"] = int(raw_idx) if raw_idx is not None else None
        spec["slide_title_hint"] = item.get("slide_title_hint") or None

    return spec


def _default_placement(
    uploads: list[ImageUploadInfo],
    artefact_kind: str,
) -> list[ImagePlacementSpec]:
    """Each upload → caption=filename without extension, all hints null.

    The deck-writer will append on new slides; the report will append at end.
    """
    result: list[ImagePlacementSpec] = []
    for upload in uploads:
        stem = PurePosixPath(upload["filename"]).stem
        spec: ImagePlacementSpec = {
            "minio_key": upload["minio_key"],
            "width_inches": _DEFAULT_WIDTH,
            "caption": stem,
        }
        if artefact_kind == "report":
            spec["section_hint"] = None
        else:
            spec["slide_index"] = None
            spec["slide_title_hint"] = None
        result.append(spec)
    return result


def _parse_llm_response(
    raw: str,
    uploads: list[ImageUploadInfo],
    artefact_kind: str,
) -> list[ImagePlacementSpec]:
    """Parse the LLM's JSON response.

    Accepts fenced ```json``` blocks and bare JSON arrays.
    Falls back to default placement when:
    - JSON is invalid / unparseable
    - Returned array length != len(uploads)
    """
    parsed = _extract_json_array(raw)

    if parsed is None:
        logger.warning(
            "image_intent.parse_failed",
            reason="invalid_json",
            raw_preview=raw[:120],
        )
        return _default_placement(uploads, artefact_kind)

    if len(parsed) != len(uploads):
        logger.warning(
            "image_intent.length_mismatch",
            expected=len(uploads),
            got=len(parsed),
        )
        return _default_placement(uploads, artefact_kind)

    specs: list[ImagePlacementSpec] = []
    for item, upload in zip(parsed, uploads):
        if not isinstance(item, dict):
            logger.warning("image_intent.item_not_dict", item=item)
            specs.append(_default_placement([upload], artefact_kind)[0])
        else:
            specs.append(_spec_from_llm_item(item, upload, artefact_kind))

    return specs


# ---------------------------------------------------------------------------
# Default LLM client factory
# ---------------------------------------------------------------------------


def _make_default_llm_client():
    """Build a ChatOpenAI client from env vars.

    Connects to the shared vLLM endpoint (Qwen) via the OpenAI-compatible API.
    temperature=0.0 for deterministic extraction; max_tokens=512 is ample for
    a short JSON array.
    """
    if ChatOpenAI is None:  # pragma: no cover
        raise ImportError("langchain-openai is required for LLM extraction")

    base_url = os.getenv("VLLM_LARGE_URL", "http://host.docker.internal:8000/v1")
    model = os.getenv("VLLM_LARGE_MODEL", "qwen-large")

    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key="dummy",  # vLLM doesn't validate the key
        temperature=0.0,
        max_tokens=512,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def extract_image_placement(
    message_text: str,
    image_uploads: list[ImageUploadInfo],
    *,
    llm_client=None,
    artefact_kind: str = "deck",
) -> list[ImagePlacementSpec]:
    """LLM-extract placement instructions from a Slack message.

    Parameters
    ----------
    message_text
        Raw Slack message text (may be empty / None).
    image_uploads
        Ordered list of uploaded image metadata (from file_handler).
    llm_client
        A langchain ChatOpenAI-compatible instance.  If None, the default
        client is constructed from VLLM_LARGE_URL / VLLM_LARGE_MODEL env vars.
    artefact_kind
        "deck" (pptx) or "report" (docx).  Controls which hints are populated.

    Returns
    -------
    list[ImagePlacementSpec]
        One spec per input upload, preserving order.  Minio keys are copied
        from the corresponding input item.  Falls back to default placement
        (all hints null, caption = filename stem) on any parse or LLM failure.
    """
    if not image_uploads:
        logger.debug("image_intent.no_uploads")
        return []

    text = (message_text or "").strip()
    if not text:
        logger.debug("image_intent.empty_message", fallback="default_placement")
        return _default_placement(image_uploads, artefact_kind)

    if llm_client is None:
        llm_client = _make_default_llm_client()

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(artefact_kind=artefact_kind)
    user_prompt = _build_extraction_prompt(text, image_uploads, artefact_kind)

    logger.info(
        "image_intent.extract_start",
        artefact_kind=artefact_kind,
        n_uploads=len(image_uploads),
        message_preview=text[:80],
    )

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await llm_client.ainvoke(messages)
        raw: str = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.warning(
            "image_intent.llm_failed",
            error=str(exc),
            fallback="default_placement",
        )
        return _default_placement(image_uploads, artefact_kind)

    specs = _parse_llm_response(raw, image_uploads, artefact_kind)

    logger.info(
        "image_intent.extract_done",
        artefact_kind=artefact_kind,
        n_specs=len(specs),
    )
    return specs
