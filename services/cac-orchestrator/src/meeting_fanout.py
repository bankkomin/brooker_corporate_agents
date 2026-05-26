"""B3 — Post-meeting subagent fan-out (LLM-powered).

When a meeting note lands in `obsidian-vault/{dept}/meeting-notes/`, this
module is invoked (via the `/events/meeting_note_landed` endpoint or
direct call from vault_watcher) and spawns N extractor workers in
parallel. Each worker produces ZERO OR MORE staging manifests:

    - entities      — counterparties / instruments mentioned
    - decisions     — committee decisions captured in the note
    - trends        — quantitative metrics / time-series observations
    - source_summary — one short summary for the dept knowledge base
    - index_update  — one mechanical append to the dept index.md

All manifests share a `source_run_id` so approval-UI groups them
as one "meeting batch" — one HOD review, N downstream files.

LLM extractors use the project's existing OpenAI-compatible endpoint
(Gemini via `vllm_large_url` / Qwen via local vLLM — same interface).
The default `_default_llm_invoker` lazily creates a langchain client;
tests inject a stub via the `llm_invoker` argument to `run_fanout`.

Hard rule (CLAUDE.md Data Safety): never writes to the vault directly.
All proposals land in /data/staging/pending/ for HOD approval.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
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

    vault_path: str = Field(description="vault-relative path, e.g. cac/meeting-notes/2026-05-26-x.md")
    dept: str
    sha256: str
    size_bytes: int


class FanoutResult(BaseModel):
    source_run_id: str
    proposal_ids: list[str]
    skipped_extractors: list[str] = Field(default_factory=list)


# Type alias: a function that takes a prompt and returns the LLM's raw text response.
LLMInvoker = Callable[[str], Awaitable[str]]


# ---------------------------------------------------------------------------
# Prompts.
#
# Each prompt asks for a strict JSON array on a single line, then we parse.
# Keeping the schemas tight; richer fields can be added later by extending
# the response schema + manifest body.
# ---------------------------------------------------------------------------


_ENTITY_PROMPT = """You extract named entities from a corporate meeting note.

Meeting note (dept: {dept}, file: {vault_path}):
---
{body}
---

Return a JSON object: {{"entities": [...]}}
Each entity has:
  - "slug": kebab-case unique slug, lowercase, no spaces
  - "display_name": canonical human name
  - "kind": one of company | instrument | regulation | concept | person | other
  - "one_liner": one sentence describing this entity as it appears in the note
  - "confidence": 0.0-1.0 your confidence this is a real entity worth tracking

Rules:
- ONLY include entities clearly named in the note. Skip vague references.
- Max 8 entities. Skip if note has none.
- Output ONLY the JSON object, no markdown, no commentary."""


_DECISION_PROMPT = """You extract committee decisions from a corporate meeting note.

Meeting note (dept: {dept}, file: {vault_path}):
---
{body}
---

Return a JSON object: {{"decisions": [...]}}
Each decision has:
  - "slug": kebab-case slug (no date prefix — that is added later)
  - "title": short imperative title
  - "outcome": one-sentence statement of what was decided
  - "rationale": one-sentence reason if stated in the note (empty string if not)
  - "binding_constraint": numeric threshold / cap / policy referenced (or empty)
  - "confidence": 0.0-1.0

Rules:
- ONLY decisions stated or implied as final. Skip "we should consider X" speculation.
- Max 6 decisions. Skip if note has none.
- Output ONLY the JSON object."""


_TREND_PROMPT = """You extract quantitative metric observations from a meeting note.

Meeting note (dept: {dept}, file: {vault_path}):
---
{body}
---

Return a JSON object: {{"trends": [...]}}
Each trend has:
  - "slug": kebab-case slug for the metric (e.g. "lcr-monthly")
  - "metric_name": canonical name
  - "value": the reported value as a string (preserve unit/sign)
  - "as_of": ISO date if stated, else empty string
  - "direction": "up" | "down" | "flat" | "unknown"
  - "confidence": 0.0-1.0

Rules:
- ONLY explicit numbers / percentages / ratios named with their metric.
- Max 8 trends. Skip if none.
- Output ONLY the JSON object."""


_SOURCE_SUMMARY_PROMPT = """You write a single short source-summary for a meeting note.

Meeting note (dept: {dept}, file: {vault_path}):
---
{body}
---

Return a JSON object: {{"summary": {{...}}}}
The summary has:
  - "title": short title (≤ 80 chars)
  - "abstract": 2-4 sentence abstract, no markdown
  - "key_terms": list of 3-7 short noun phrases
  - "confidence": 0.0-1.0

Output ONLY the JSON object."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_code_fence(text: str) -> str:
    """LLMs often wrap JSON in ```json ... ```; strip it."""
    text = text.strip()
    if text.startswith("```"):
        # Remove first line (``` or ```json) and trailing ```
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _safe_json(text: str) -> dict:
    """Parse JSON; return empty dict on failure."""
    try:
        return json.loads(_strip_code_fence(text))
    except (json.JSONDecodeError, ValueError):
        log.warning("meeting_fanout: LLM returned non-JSON; body head=%r", text[:200])
        return {}


def _clamp_confidence(c: object, default: float = 0.5) -> float:
    try:
        v = float(c)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, v))


def _safe_slug(s: str, fallback: str) -> str:
    """Kebab-case-ify; fall back if the LLM returned junk."""
    if not isinstance(s, str) or not s.strip():
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", s.strip().lower()).strip("-")
    return cleaned or fallback


async def _default_llm_invoker(prompt: str) -> str:  # pragma: no cover — needs running LLM
    """Production LLM caller. Lazily imports ChatOpenAI so unit tests don't
    require the dep when they inject their own invoker."""
    from langchain_openai import ChatOpenAI

    from .config import settings

    llm = ChatOpenAI(
        base_url=settings.vllm_large_url,
        model=settings.vllm_large_model,
        api_key=settings.llm_api_key or "not-needed",
        temperature=0.1,
    )
    resp = await llm.ainvoke(prompt)
    return getattr(resp, "content", "") or ""


# ---------------------------------------------------------------------------
# Extractors — each returns a list of manifests (possibly empty).
# ---------------------------------------------------------------------------


async def _extract_entities(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str,
    today: date, llm: LLMInvoker,
) -> list[VaultStagingManifest]:
    prompt = _ENTITY_PROMPT.format(dept=event.dept, vault_path=event.vault_path, body=body[:8000])
    raw = await llm(prompt)
    data = _safe_json(raw)
    entities = data.get("entities", [])
    if not isinstance(entities, list):
        return []
    out: list[VaultStagingManifest] = []
    for ent in entities[:8]:
        if not isinstance(ent, dict):
            continue
        slug = _safe_slug(ent.get("slug", ""), fallback=_safe_slug(ent.get("display_name", ""), "unknown"))
        display = str(ent.get("display_name", slug))
        kind = str(ent.get("kind", "concept"))
        one_liner = str(ent.get("one_liner", "")).strip()
        conf = _clamp_confidence(ent.get("confidence", 0.6))
        draft = (
            "---\n"
            f"title: \"{display}\"\n"
            "type: entity\n"
            f"department: {event.dept}\n"
            f"kind: {kind}\n"
            f"sources: [\"{event.vault_path}\"]\n"
            f"created: {today.isoformat()}\n"
            f"updated: {today.isoformat()}\n"
            "tags: [entity, extracted]\n"
            "---\n\n"
            f"# {display}\n\n"
            "## TL;DR for Agents\n"
            f"**Retrieved by:** [[skills/{event.dept}/]]\n"
            f"**Answers:** \"Who/what is {display}?\"\n"
            f"**Key facts:** {one_liner or 'TODO'}\n\n"
            "## Summary\n\n"
            f"{one_liner or 'TODO — populated from meeting context.'}\n\n"
            "## Source References\n"
            f"- `{event.vault_path}`\n"
        )
        out.append(build_manifest(
            agent="meeting-extractor-entities",
            dept=event.dept,
            target_vault_path=f"{event.dept}/entities/{slug}.md",
            operation="create",
            draft_content=draft,
            confidence=conf,
            reasoning=f"Extracted from meeting note. {one_liner[:100] or ''}",
            proposal_source="vault_automation",
            extracted_from=event.vault_path,
            source_run_id=source_run_id,
        ))
    return out


async def _extract_decisions(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str,
    today: date, llm: LLMInvoker,
) -> list[VaultStagingManifest]:
    prompt = _DECISION_PROMPT.format(dept=event.dept, vault_path=event.vault_path, body=body[:8000])
    raw = await llm(prompt)
    data = _safe_json(raw)
    decisions = data.get("decisions", [])
    if not isinstance(decisions, list):
        return []
    out: list[VaultStagingManifest] = []
    for dec in decisions[:6]:
        if not isinstance(dec, dict):
            continue
        slug = _safe_slug(dec.get("slug", ""), fallback="decision")
        title = str(dec.get("title", "Untitled decision"))
        outcome = str(dec.get("outcome", "")).strip()
        rationale = str(dec.get("rationale", "")).strip()
        constraint = str(dec.get("binding_constraint", "")).strip()
        conf = _clamp_confidence(dec.get("confidence", 0.6))
        date_iso = today.isoformat()
        draft = (
            "---\n"
            f"date: \"{date_iso}\"\n"
            "type: decision\n"
            f"committee: {event.dept.upper()}\n"
            f"decision-id: \"{event.dept.upper()}-{date_iso}-extracted\"\n"
            "status: active\n"
            f"sources: [\"{event.vault_path}\"]\n"
            "tags: [decision, extracted]\n"
            "---\n\n"
            f"# Decision: {title}\n\n"
            "## TL;DR for Agents\n"
            f"**Retrieved by:** [[skills/{event.dept}/]]\n"
            f"**Answers:** \"What was decided on {title.lower()}?\"\n"
            f"**Key facts:** {outcome or 'TODO'} {('Constraint: ' + constraint) if constraint else ''}\n\n"
            "## Context\n"
            f"Extracted from `{event.vault_path}`.\n\n"
            "## Decision\n"
            f"{outcome or 'TODO'}\n\n"
            "## Rationale\n"
            f"{rationale or 'See source meeting note.'}\n\n"
            "## Approved By\n"
            "- TODO — confirm during review.\n"
        )
        out.append(build_manifest(
            agent="meeting-extractor-decisions",
            dept=event.dept,
            target_vault_path=f"{event.dept}/decisions/{date_iso}-{slug}.md",
            operation="create",
            draft_content=draft,
            confidence=conf,
            reasoning=outcome[:200],
            proposal_source="vault_automation",
            extracted_from=event.vault_path,
            source_run_id=source_run_id,
        ))
    return out


async def _extract_trends(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str,
    today: date, llm: LLMInvoker,
) -> list[VaultStagingManifest]:
    prompt = _TREND_PROMPT.format(dept=event.dept, vault_path=event.vault_path, body=body[:8000])
    raw = await llm(prompt)
    data = _safe_json(raw)
    trends = data.get("trends", [])
    if not isinstance(trends, list):
        return []
    out: list[VaultStagingManifest] = []
    for tr in trends[:8]:
        if not isinstance(tr, dict):
            continue
        slug = _safe_slug(tr.get("slug", ""), fallback="trend")
        metric = str(tr.get("metric_name", slug))
        value = str(tr.get("value", "")).strip()
        as_of = str(tr.get("as_of", "")).strip() or today.isoformat()
        direction = str(tr.get("direction", "unknown")).lower()
        conf = _clamp_confidence(tr.get("confidence", 0.6))
        draft = (
            "---\n"
            f"title: \"{metric}\"\n"
            "type: trend\n"
            f"department: {event.dept}\n"
            f"created: {today.isoformat()}\n"
            f"updated: {today.isoformat()}\n"
            f"sources: [\"{event.vault_path}\"]\n"
            "tags: [trend, extracted]\n"
            "---\n\n"
            f"# {metric}\n\n"
            "## Observation\n"
            f"- **Value:** {value}\n"
            f"- **As of:** {as_of}\n"
            f"- **Direction:** {direction}\n"
            f"- **Source:** `{event.vault_path}`\n"
        )
        out.append(build_manifest(
            agent="meeting-extractor-trends",
            dept=event.dept,
            target_vault_path=f"{event.dept}/trends/{today.isoformat()}-{slug}.md",
            operation="create",
            draft_content=draft,
            confidence=conf,
            reasoning=f"{metric} = {value} (as of {as_of})",
            proposal_source="vault_automation",
            extracted_from=event.vault_path,
            source_run_id=source_run_id,
        ))
    return out


async def _extract_source_summary(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str,
    today: date, llm: LLMInvoker,
) -> list[VaultStagingManifest]:
    prompt = _SOURCE_SUMMARY_PROMPT.format(dept=event.dept, vault_path=event.vault_path, body=body[:8000])
    raw = await llm(prompt)
    data = _safe_json(raw)
    summary = data.get("summary") or {}
    if not isinstance(summary, dict):
        return []
    title = str(summary.get("title", Path(event.vault_path).stem))[:120]
    abstract = str(summary.get("abstract", "")).strip()
    key_terms = summary.get("key_terms", [])
    if not isinstance(key_terms, list):
        key_terms = []
    conf = _clamp_confidence(summary.get("confidence", 0.7))
    if not abstract:
        return []  # Don't propose empty summaries
    rel_stem = Path(event.vault_path).stem
    tags_list = "[" + ", ".join(f"\"{t}\"" for t in key_terms[:7]) + "]"
    draft = (
        "---\n"
        f"title: \"{title}\"\n"
        "type: source-summary\n"
        f"department: {event.dept}\n"
        f"created: {today.isoformat()}\n"
        f"source_file: \"{event.vault_path}\"\n"
        f"key_terms: {tags_list}\n"
        "tags: [source-summary, extracted]\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Abstract\n"
        f"{abstract}\n\n"
        "## Key terms\n"
        + "\n".join(f"- {t}" for t in key_terms[:7])
        + ("\n" if key_terms else "(none extracted)\n")
    )
    return [build_manifest(
        agent="meeting-extractor-source-summary",
        dept=event.dept,
        target_vault_path=f"{event.dept}/source-summaries/{today.isoformat()}-{rel_stem}.md",
        operation="create",
        draft_content=draft,
        confidence=conf,
        reasoning=f"Summary of {event.vault_path}: {abstract[:100]}",
        proposal_source="vault_automation",
        extracted_from=event.vault_path,
        source_run_id=source_run_id,
    )]


async def _extract_index_update(
    *, event: MeetingNoteLandedEvent, body: str, source_run_id: str,
    today: date, llm: LLMInvoker,
) -> list[VaultStagingManifest]:
    """Mechanical — does not call the LLM. Append a meeting-notes bullet to {dept}/index.md."""
    rel_name = Path(event.vault_path).stem
    snippet = f"- [[{event.dept}/meeting-notes/{rel_name}|{rel_name}]] *(auto-linked)*\n"
    return [build_manifest(
        agent="meeting-extractor-index-update",
        dept=event.dept,
        target_vault_path=f"{event.dept}/index.md",
        operation="append",
        draft_content=snippet,
        confidence=0.95,
        reasoning=f"Add meeting-note bullet for {rel_name} to {event.dept}/index.md",
        proposal_source="vault_automation",
        extracted_from=event.vault_path,
        source_run_id=source_run_id,
    )]


ExtractorFn = Callable[..., Awaitable[list[VaultStagingManifest]]]

EXTRACTORS: dict[str, ExtractorFn] = {
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
    llm_invoker: LLMInvoker | None = None,
) -> FanoutResult:
    """Read the meeting note and spawn extractors in parallel.

    Each extractor returns 0..N manifests. All manifests share a
    `source_run_id` derived from the file hash. Failures in one
    extractor never block the others.

    Pass `llm_invoker=` in tests to inject deterministic LLM output.
    Default is the project LLM (Gemini/Qwen via OpenAI-compatible API).
    """
    today = today or date.today()
    source_run_id = f"meetfan_{event.sha256[:8]}"
    llm = llm_invoker or _default_llm_invoker

    full_path = Path(vault_root) / event.vault_path
    if not full_path.is_file():
        log.error("meeting_fanout: meeting note not found at %s", full_path)
        return FanoutResult(source_run_id=source_run_id, proposal_ids=[])
    body = full_path.read_text(encoding="utf-8", errors="ignore")

    # Run extractors concurrently
    async def _safe_call(name: str, fn: ExtractorFn) -> tuple[str, list[VaultStagingManifest] | Exception]:
        try:
            out = await fn(
                event=event, body=body, source_run_id=source_run_id, today=today, llm=llm,
            )
            return name, out
        except Exception as exc:  # noqa: BLE001 — isolate worker failures
            log.exception("meeting_fanout: extractor %s raised", name)
            return name, exc

    results = await asyncio.gather(
        *[_safe_call(name, fn) for name, fn in EXTRACTORS.items()]
    )

    manifests: list[VaultStagingManifest] = []
    skipped: list[str] = []
    for name, res in results:
        if isinstance(res, Exception):
            skipped.append(name)
        elif not res:
            skipped.append(name)
        else:
            manifests.extend(res)

    # Write all manifests in parallel
    write_results = await asyncio.gather(
        *[write_vault_staging(m, staging_path=staging_path) for m in manifests],
        return_exceptions=True,
    )
    proposal_ids: list[str] = []
    for m, res in zip(manifests, write_results):
        if isinstance(res, Exception) or res is None:
            log.warning("meeting_fanout: write failed for %s", m.agent)
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
