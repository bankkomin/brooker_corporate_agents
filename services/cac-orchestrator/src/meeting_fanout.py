"""B3 — Post-meeting subagent fan-out.

When a meeting note lands in `obsidian-vault/{dept}/meeting-notes/`, this
module is invoked (via the `/events/meeting_note_landed` endpoint or
direct call from vault_watcher) and spawns N parallel extractor workers.
Each worker produces ONE staging manifest of a specific artifact type:

    - entities      — counterparties / instruments mentioned
    - decisions     — committee decisions captured in the note
    - trends        — quantitative metrics / time-series observations
    - source_summary — short summary for the dept knowledge base
    - index_update  — proposed index.md update for the dept

All five manifests share a `source_run_id` so approval-UI can group them
as one "meeting batch" — one HOD review, multiple downstream files.

Current state: extractors are deterministic stubs that produce
real-shaped manifests with `confidence=0.0` and TODO-marked draft
content. A future commit replaces each `_extract_*` body with an
actual LLM call. The plumbing — event handling, parallel dispatch,
manifest schema, staging-pipeline write — is fully working.

Hard rule: never writes to the vault directly. All proposals land in
/data/staging/pending/ for HOD approval.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable

from pydantic import BaseModel, Field

try:
    from services.shared.vault_staging import (
        VaultStagingManifest,
        build_manifest,
        write_vault_staging,
    )
except ImportError:  # pragma: no cover — fallback for in-service test runs
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from services.shared.vault_staging import (
        VaultStagingManifest,
        build_manifest,
        write_vault_staging,
    )

log = logging.getLogger(__name__)


class MeetingNoteLandedEvent(BaseModel):
    """Event payload from vault_watcher (or any other trigger)."""

    vault_path: str = Field(description="vault-relative path, e.g. obsidian-vault/cac/meeting-notes/2026-05-26-x.md")
    dept: str
    sha256: str
    size_bytes: int


class FanoutResult(BaseModel):
    source_run_id: str
    proposal_ids: list[str]
    skipped_extractors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Extractor stubs.
#
# Each extractor reads the meeting note body and returns a
# VaultStagingManifest describing one proposed vault write. Replace the
# bodies with real LLM calls in a future commit; the plumbing around them
# is final.
# ---------------------------------------------------------------------------


def _extract_entities(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str, today: date
) -> VaultStagingManifest | None:
    """Stub: would extract counterparty / instrument names from `body` and
    propose `{dept}/entities/{slug}.md` create-or-update manifests.

    For now we emit a single placeholder manifest so the downstream pipeline
    can be wired and tested. Real implementation: prompt Qwen 122B with
    `body` + few-shot examples, parse a JSON list of entities, build one
    manifest per entity.
    """
    draft = (
        "---\n"
        "type: entity\n"
        f"department: {event.dept}\n"
        "extracted: true\n"
        "---\n"
        "# TODO — entity extraction stub\n\n"
        f"Source meeting note: `{event.vault_path}`\n\n"
        "_The LLM-driven entity extractor has not been wired yet. This is a "
        "placeholder manifest so the fan-out pipeline can be exercised end-to-end._\n"
    )
    return build_manifest(
        agent="meeting-extractor-entities",
        dept=event.dept,
        target_vault_path=f"{event.dept}/entities/_pending-extraction-{source_run_id}.md",
        operation="create",
        draft_content=draft,
        confidence=0.0,  # stub — real extractor sets per-entity confidence
        reasoning="Stub manifest. LLM extraction not yet wired.",
        proposal_source="vault_automation",
        extracted_from=event.vault_path,
        source_run_id=source_run_id,
    )


def _extract_decisions(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str, today: date
) -> VaultStagingManifest | None:
    """Stub: propose `{dept}/decisions/YYYY-MM-DD-{slug}.md` per decision in body."""
    draft = (
        "---\n"
        "type: decision\n"
        f"committee: {event.dept.upper()}\n"
        f"date: {today.isoformat()}\n"
        "extracted: true\n"
        "tags: [decision, extracted]\n"
        "---\n"
        "# Decision: TODO\n\n"
        "## TL;DR for Agents\n"
        "**Retrieved by:** TODO\n"
        "**Answers:** \"TODO\"\n"
        "**Key facts:** TODO\n\n"
        f"_Extracted from `{event.vault_path}`. LLM populates the rest._\n"
    )
    return build_manifest(
        agent="meeting-extractor-decisions",
        dept=event.dept,
        target_vault_path=f"{event.dept}/decisions/{today.isoformat()}-pending-extraction-{source_run_id}.md",
        operation="create",
        draft_content=draft,
        confidence=0.0,
        reasoning="Stub manifest. LLM extraction not yet wired.",
        proposal_source="vault_automation",
        extracted_from=event.vault_path,
        source_run_id=source_run_id,
    )


def _extract_trends(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str, today: date
) -> VaultStagingManifest | None:
    draft = (
        "---\n"
        "type: trend\n"
        f"department: {event.dept}\n"
        f"created: {today.isoformat()}\n"
        "extracted: true\n"
        "---\n"
        "# Trend snapshot — TODO\n\n"
        f"_From `{event.vault_path}`. LLM extracts quantitative observations._\n"
    )
    return build_manifest(
        agent="meeting-extractor-trends",
        dept=event.dept,
        target_vault_path=f"{event.dept}/trends/{today.isoformat()}-pending-extraction-{source_run_id}.md",
        operation="create",
        draft_content=draft,
        confidence=0.0,
        reasoning="Stub manifest. LLM extraction not yet wired.",
        proposal_source="vault_automation",
        extracted_from=event.vault_path,
        source_run_id=source_run_id,
    )


def _extract_source_summary(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str, today: date
) -> VaultStagingManifest | None:
    draft = (
        "---\n"
        "type: source-summary\n"
        f"department: {event.dept}\n"
        f"created: {today.isoformat()}\n"
        f"source_file: {event.vault_path}\n"
        "---\n"
        "# Source summary — TODO\n\n"
        "_Auto-summarized at ingest. LLM populates abstract + key terms._\n"
    )
    return build_manifest(
        agent="meeting-extractor-source-summary",
        dept=event.dept,
        target_vault_path=f"{event.dept}/source-summaries/{today.isoformat()}-pending-extraction-{source_run_id}.md",
        operation="create",
        draft_content=draft,
        confidence=0.0,
        reasoning="Stub manifest. LLM extraction not yet wired.",
        proposal_source="vault_automation",
        extracted_from=event.vault_path,
        source_run_id=source_run_id,
    )


def _extract_index_update(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str, today: date
) -> VaultStagingManifest | None:
    """Append a meeting-notes bullet to {dept}/index.md."""
    rel_name = Path(event.vault_path).stem
    snippet = f"- [[{event.dept}/meeting-notes/{rel_name}|{rel_name}]] *(auto-linked)*\n"
    return build_manifest(
        agent="meeting-extractor-index-update",
        dept=event.dept,
        target_vault_path=f"{event.dept}/index.md",
        operation="append",
        draft_content=snippet,
        confidence=0.95,  # mechanical append, high confidence
        reasoning=f"Add meeting-note bullet for {rel_name} to {event.dept}/index.md",
        proposal_source="vault_automation",
        extracted_from=event.vault_path,
        source_run_id=source_run_id,
    )


EXTRACTORS: dict[str, Callable[..., VaultStagingManifest | None]] = {
    "entities": _extract_entities,
    "decisions": _extract_decisions,
    "trends": _extract_trends,
    "source_summary": _extract_source_summary,
    "index_update": _extract_index_update,
}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run_fanout(
    event: MeetingNoteLandedEvent,
    *,
    staging_path: str,
    vault_root: str,
    today: date | None = None,
) -> FanoutResult:
    """Read the meeting note and spawn N parallel extractor stubs.

    Returns a FanoutResult with all written proposal ids grouped by a
    shared source_run_id. Failures in one extractor do not block the
    others (asyncio.gather with return_exceptions=True).
    """
    today = today or date.today()
    source_run_id = f"meetfan_{event.sha256[:8]}"

    full_path = Path(vault_root) / event.vault_path
    if not full_path.is_file():
        log.error("meeting_fanout: meeting note not found at %s", full_path)
        return FanoutResult(source_run_id=source_run_id, proposal_ids=[])
    body = full_path.read_text(encoding="utf-8", errors="ignore")

    # Build all manifests in parallel (extractors are sync today; gather lets
    # us swap individual ones for async LLM calls later without restructuring).
    manifests: list[VaultStagingManifest] = []
    skipped: list[str] = []
    for name, extractor in EXTRACTORS.items():
        try:
            m = extractor(event=event, body=body, source_run_id=source_run_id, today=today)
        except Exception:
            log.exception("meeting_fanout: extractor %s raised", name)
            skipped.append(name)
            continue
        if m is None:
            skipped.append(name)
        else:
            manifests.append(m)

    # Write all manifests in parallel
    write_tasks: list[Awaitable[str | None]] = [
        write_vault_staging(m, staging_path=staging_path) for m in manifests
    ]
    results = await asyncio.gather(*write_tasks, return_exceptions=True)

    proposal_ids: list[str] = []
    for m, res in zip(manifests, results):
        if isinstance(res, Exception):
            log.exception("meeting_fanout: write failed for %s", m.agent, exc_info=res)
            skipped.append(m.agent)
        elif res is None:
            skipped.append(m.agent)
        else:
            proposal_ids.append(res)

    log.info(
        "meeting_fanout: source_run_id=%s wrote=%d skipped=%d for %s",
        source_run_id, len(proposal_ids), len(skipped), event.vault_path,
    )
    return FanoutResult(
        source_run_id=source_run_id,
        proposal_ids=proposal_ids,
        skipped_extractors=skipped,
    )
