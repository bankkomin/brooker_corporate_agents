"""Staging-proposal writer for write-tier departments.

DATA SAFETY: this module ONLY writes to /data/staging/pending/.
It NEVER touches /data/mirror/ or any live corporate system.
The staging path is always derived from settings.STAGING_PATH, which must
point to Zone 2 (staging). Docker enforces /data/mirror/ as :ro.

A manifest is written when ALL of the following are true:
  1. dept capabilityTier == "write"
  2. The LLM answer contains a clearly structured proposed change
     (proposed_value is non-empty after extraction)
  3. confidence >= settings.STAGING_CONFIDENCE_THRESHOLD (default 0.85)

For read_only departments (including ic which is read_only in departments.json)
no manifest is ever written — the function returns None immediately.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Manifest schema (mirrors CLAUDE.md "Staging Proposal Manifest Schema" exactly)
# ---------------------------------------------------------------------------

class StagingManifest(BaseModel):
    """Pydantic v2 model for the staging proposal manifest written to disk."""

    id: str
    agent: str
    dept_id: str
    file: str | None
    tab: str | None
    cell: str | None
    old_value: str | None = None
    new_value: str
    source: str
    confidence: float
    reasoning: str
    status: str = "pending"
    schema_missing: bool = Field(
        default=False,
        description="True when no Excel schema was found for this department.",
    )
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    specialist: str | None = None


# ---------------------------------------------------------------------------
# Proposal detection — conservative regex-based extraction
# ---------------------------------------------------------------------------

# Patterns that signal the model is proposing a concrete value change.
# Only match when a numeric/monetary value and a clear "change/update/propose"
# verb appear together. We are deliberately conservative: false negatives are
# safer than false positives (which would create junk manifests).
_PROPOSE_RE = re.compile(
    r"(?:propose|recommend|suggest|update|change|set|revise)\s+"
    r"(?:the\s+)?(?P<field>[\w\s/()%-]{2,40}?)\s+"
    r"(?:to|from\s+[\w.,%-]+\s+to)\s+"
    r"(?P<value>[+-]?[\d,]+(?:\.\d+)?(?:\s*(?:%|[A-Z]{2,5}|bp|bps))?)",
    re.IGNORECASE,
)

# Secondary pattern: "X should be / is now Y"
_SHOULD_BE_RE = re.compile(
    r"(?P<field>[\w\s/()%-]{2,40}?)\s+should\s+be\s+(?:updated\s+to\s+)?(?P<value>[+-]?[\d,]+(?:\.\d+)?(?:\s*(?:%|[A-Z]{2,5}|bp|bps))?)",
    re.IGNORECASE,
)


def _extract_proposal(answer: str) -> tuple[str | None, str | None]:
    """Return (field_hint, proposed_value) or (None, None) if no concrete
    change is detected.  Deliberately conservative — only clear numeric
    value-change sentences qualify."""
    for pattern in (_PROPOSE_RE, _SHOULD_BE_RE):
        m = pattern.search(answer)
        if m:
            field = m.group("field").strip()
            value = m.group("value").strip()
            if value:
                return field, value
    return None, None


# ---------------------------------------------------------------------------
# Excel schema lookup — best-effort only, never invents precise cells
# ---------------------------------------------------------------------------

def _lookup_excel_schema(dept_id: str, field_hint: str | None) -> tuple[str | None, str | None, str | None, bool]:
    """Return (file, tab, cell, schema_missing).

    Searches config/excel_schema/{dept_id}_*.json for a tab/column matching
    field_hint. If no schema exists or no match is found, returns nulls and
    schema_missing=True. We NEVER invent precise cell coordinates.
    """
    schema_dir = Path(settings.EXCEL_SCHEMA_DIR)
    dept_schemas = sorted(schema_dir.glob(f"{dept_id}_*.json"))
    if not dept_schemas:
        return None, None, None, True  # no schema for this dept

    # Use the first schema file found for this dept
    schema_file = dept_schemas[0]
    try:
        schema: dict[str, Any] = json.loads(schema_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("excel_schema_read_failed dept=%s err=%r", dept_id, exc)
        return None, None, None, True

    excel_file: str | None = schema.get("file") or schema.get("filename")
    tabs: list[dict] = schema.get("tabs") or schema.get("sheets") or []

    if not field_hint or not tabs:
        return excel_file, None, None, False

    field_lower = field_hint.lower()
    for tab in tabs:
        tab_name: str = tab.get("name") or tab.get("tab") or ""
        columns: list[dict] = tab.get("columns") or tab.get("fields") or []
        for col in columns:
            col_name: str = (col.get("name") or col.get("column") or "").lower()
            if field_lower in col_name or col_name in field_lower:
                # Found a matching column — we know the tab and column header,
                # but NOT the exact row. Return tab + column letter if present;
                # never fabricate a row number.
                col_letter: str | None = col.get("column_letter") or col.get("letter")
                cell_ref = col_letter if col_letter else None  # no row = no precise cell
                return excel_file, tab_name, cell_ref, False

    # Schema exists but no column matched — still a useful partial hit
    return excel_file, None, None, False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _next_proposal_id() -> str:
    return f"chg_{uuid.uuid4().hex[:8]}"


async def maybe_write_staging_proposal(
    *,
    dept_id: str,
    dept_config: dict,
    answer: str,
    query: str,
    user_id: str,
    specialist: str | None,
    top_chunk_score: float,
) -> str | None:
    """Write a staging manifest if the dept is write-tier and a concrete
    change proposal is detected above the confidence threshold.

    Returns the proposal_id string if a manifest was written, else None.

    SAFETY: writes exclusively to {STAGING_PATH}/pending/{dept_id}/.
    Never writes to /data/mirror/ or any other path.
    """
    capability_tier: str = dept_config.get("capabilityTier", "read_only")

    # Gate 1: department must be write-tier
    if capability_tier != "write":
        log.debug(
            "staging_skipped_read_only dept=%s tier=%s", dept_id, capability_tier
        )
        return None

    # Gate 2: confidence threshold (use the best RAG score as a proxy for
    # answer confidence — same number drives the grounding gate above)
    if top_chunk_score < settings.STAGING_CONFIDENCE_THRESHOLD:
        log.info(
            "staging_skipped_low_confidence dept=%s score=%.3f threshold=%.2f",
            dept_id,
            top_chunk_score,
            settings.STAGING_CONFIDENCE_THRESHOLD,
        )
        return None

    # Gate 3: detect a concrete proposed change in the answer
    field_hint, proposed_value = _extract_proposal(answer)
    if not proposed_value:
        log.debug("staging_skipped_no_proposal dept=%s", dept_id)
        return None

    # Best-effort Excel schema lookup
    excel_file, tab, cell, schema_missing = _lookup_excel_schema(dept_id, field_hint)

    proposal_id = _next_proposal_id()

    dept_name: str = dept_config.get("name", dept_id)
    agent_name: str = (
        (dept_config.get("agentTopology") or {}).get("orchestrator")
        or f"{dept_id}-agent"
    )

    manifest = StagingManifest(
        id=proposal_id,
        agent=agent_name,
        dept_id=dept_id,
        file=excel_file,
        tab=tab,
        cell=cell,
        new_value=proposed_value,
        source=f"read-only-orchestrator | {dept_name} | {user_id} | {datetime.now(UTC).date().isoformat()}",
        confidence=top_chunk_score,
        reasoning=answer[:500],
        schema_missing=schema_missing,
        specialist=specialist,
    )

    # Write to Zone 2 ONLY — /data/staging/pending/{dept_id}/
    # This is the ONLY write path. /data/mirror/ is never touched here.
    staging_dir = Path(settings.STAGING_PATH) / "pending" / dept_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = staging_dir / f"{proposal_id}.json"

    try:
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        log.error(
            "staging_write_failed dept=%s id=%s error=%r", dept_id, proposal_id, exc
        )
        return None

    log.info(
        "staging_proposal_written dept=%s id=%s path=%s schema_missing=%s",
        dept_id,
        proposal_id,
        manifest_path,
        schema_missing,
    )
    return proposal_id
