"""B4 — Turn synthesis_tracker candidates into vault staging manifests.

For each (entity, dept) pair whose distinct-source count has crossed the
per-dept threshold (config/synthesis_thresholds.json), this module:

1. Embeds the entity display name.
2. Searches the dept's `{dept}_docs` and `{dept}_knowledge` Qdrant
   collections for representative chunks.
3. Calls the LLM with those chunks to draft a concept note.
4. Writes a `VaultStagingManifest` (operation=create, target
   `{dept}/concepts/{entity}.md`) to `/data/staging/pending/`.
5. Marks the (entity, dept) pair `proposed_pending` in synthesis_state
   so we don't re-propose tomorrow.

Hard rule (CLAUDE.md Data Safety): never writes to the vault directly.
All proposed concept notes require HOD approval via approval-ui.

The module is designed to be invoked on a schedule (nightly is typical)
or via a manual `POST /synthesis/scan` endpoint. It's idempotent: a
candidate that's already `proposed_pending` is skipped by
`find_synthesis_candidates`.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Awaitable, Callable, Iterable

from .synthesis_tracker import (
    SynthesisCandidate,
    find_synthesis_candidates,
    load_thresholds,
    mark_proposed,
)

try:
    from services.shared.vault_staging import build_manifest, write_vault_staging
except ImportError:  # pragma: no cover
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from services.shared.vault_staging import build_manifest, write_vault_staging

log = logging.getLogger(__name__)

LLMInvoker = Callable[[str], Awaitable[str]]


_CONCEPT_PROMPT = """You draft a corporate knowledge-base concept article for the {dept} department.

Entity: {entity_display}  (kind hint: {kind_hint})
Distinct source documents referencing this entity: {source_count} (threshold: {threshold_used})

Representative passages from those sources:
{passages}

Write the concept article BODY ONLY — frontmatter is added by the system.
Use this skeleton:

# {entity_display}

## TL;DR for Agents
**Retrieved by:** [[skills/{dept}/]]
**Answers:** "One short question this concept resolves."
**Key facts:** 1-2 sentences with the most decision-relevant facts. Use inline `(as of YYYY-MM, source)` markers for quantitative claims.

## Summary
One paragraph plain-language description.

## Definition
Precise definition (regulatory citation if applicable).

## Why It Matters
Two-to-four sentences on business or regulatory significance for {dept}.

## Source References
Bulleted list of the source documents observed (use exact filenames).

Output ONLY the markdown body. Do not include frontmatter or any commentary."""


async def _passages_for_entity(
    *, entity_display: str, dept: str, embedder, store, limit: int = 6,
) -> list[dict]:
    """Embed entity name and pull top-K chunks from {dept}_docs + {dept}_knowledge."""
    vector = await embedder.embed_texts([entity_display])
    if not vector or not vector[0]:
        return []
    query_vec = vector[0]
    out: list[dict] = []
    for coll in (f"{dept}_docs", f"{dept}_knowledge"):
        try:
            hits = await store.search(
                collection=coll, query_vector=query_vec,
                limit=limit, score_threshold=0.6,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("synthesis_proposer.search_failed collection=%s err=%s", coll, exc)
            continue
        out.extend(hits)
    # Best-N by score
    out.sort(key=lambda h: h.get("score", 0.0), reverse=True)
    return out[:limit]


def _render_passages(hits: Iterable[dict]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        src = h.get("source_file") or h.get("filename") or "(unknown source)"
        text = h.get("text", "")[:500].replace("\n", " ")
        lines.append(f"[{i}] (from {src}): {text}")
    return "\n\n".join(lines) if lines else "(no passages retrieved — proceed conservatively)"


def _source_files_from(hits: Iterable[dict]) -> list[str]:
    seen: list[str] = []
    for h in hits:
        src = h.get("source_file") or h.get("filename")
        if src and src not in seen:
            seen.append(src)
    return seen


def _build_frontmatter(
    *, entity_slug: str, entity_display: str, dept: str, sources: list[str], today: date,
) -> str:
    src_lines = "[" + ", ".join(f"\"{s}\"" for s in sources) + "]"
    return (
        "---\n"
        f"title: \"{entity_display}\"\n"
        "type: \"concept\"\n"
        f"department: \"{dept}\"\n"
        f"sources: {src_lines}\n"
        f"related: []\n"
        f"created: \"{today.isoformat()}\"\n"
        f"updated: \"{today.isoformat()}\"\n"
        f"event_date: \"\"\n"
        f"confidence: \"medium\"\n"
        f"coverage: \"low\"\n"
        "tags: [concept, auto-synthesized]\n"
        "---\n\n"
    )


async def propose_for_candidate(
    candidate: SynthesisCandidate,
    *,
    pool,
    embedder,
    store,
    staging_path: str,
    llm: LLMInvoker,
    entity_display_lookup: dict[str, str] | None = None,
    today: date | None = None,
) -> str | None:
    """Draft a concept note for one candidate and write it to staging.

    Returns the proposal id, or None if no usable passages / LLM output.
    On success, the candidate is marked `proposed_pending` in synthesis_state.

    `entity_display_lookup` maps slug -> display_name. If absent, falls
    back to a titlecased version of the slug.
    """
    today = today or date.today()
    entity_display = (entity_display_lookup or {}).get(candidate.entity) or candidate.entity.replace("-", " ").title()
    hits = await _passages_for_entity(
        entity_display=entity_display, dept=candidate.dept, embedder=embedder, store=store,
    )
    passages = _render_passages(hits)
    sources = _source_files_from(hits)

    prompt = _CONCEPT_PROMPT.format(
        dept=candidate.dept,
        entity_display=entity_display,
        kind_hint="concept",  # entity_kind not joined yet; cheap to add later
        source_count=candidate.source_count,
        threshold_used=candidate.threshold_used,
        passages=passages,
    )
    try:
        body = await llm(prompt)
    except Exception as exc:  # noqa: BLE001
        log.warning("synthesis_proposer.llm_failed entity=%s err=%s", candidate.entity, exc)
        return None
    body = body.strip()
    if not body:
        log.info("synthesis_proposer: empty LLM body for %s", candidate.entity)
        return None

    frontmatter = _build_frontmatter(
        entity_slug=candidate.entity, entity_display=entity_display,
        dept=candidate.dept, sources=sources, today=today,
    )
    draft = frontmatter + body + "\n"

    manifest = build_manifest(
        agent="synthesis-proposer",
        dept=candidate.dept,
        target_vault_path=f"{candidate.dept}/concepts/{candidate.entity}.md",
        operation="create",
        draft_content=draft,
        confidence=0.75,
        reasoning=(
            f"Auto-synthesis: {entity_display} appeared in {candidate.source_count} "
            f"distinct source docs (threshold {candidate.threshold_used})."
        ),
        proposal_source="vault_automation",
        synthesis_evidence={
            "entity": candidate.entity,
            "entity_display": entity_display,
            "source_count": candidate.source_count,
            "threshold_used": candidate.threshold_used,
            "sources": sources,
        },
    )
    pid = await write_vault_staging(manifest, staging_path=staging_path)
    if pid is not None:
        await mark_proposed(pool, entity=candidate.entity, dept=candidate.dept, proposal_id=pid)
    return pid


async def scan_and_propose(
    *,
    pool,
    embedder,
    store,
    staging_path: str,
    llm: LLMInvoker,
    thresholds_path: str | Path = "/app/config/synthesis_thresholds.json",
    today: date | None = None,
) -> dict:
    """Run one synthesis sweep. Returns {'candidates': N, 'proposed': N, 'skipped': N}."""
    thresholds = load_thresholds(thresholds_path)
    candidates = await find_synthesis_candidates(pool, thresholds=thresholds)
    proposed: list[str] = []
    skipped: list[str] = []
    for c in candidates:
        pid = await propose_for_candidate(
            c, pool=pool, embedder=embedder, store=store,
            staging_path=staging_path, llm=llm, today=today,
        )
        if pid:
            proposed.append(pid)
        else:
            skipped.append(c.entity)
    log.info(
        "synthesis_proposer.scan_complete candidates=%d proposed=%d skipped=%d",
        len(candidates), len(proposed), len(skipped),
    )
    return {
        "candidates": len(candidates),
        "proposed": len(proposed),
        "proposal_ids": proposed,
        "skipped": skipped,
    }
