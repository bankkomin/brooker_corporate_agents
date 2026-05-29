"""B4 — Entity-mention tracker + synthesis-proposal trigger.

Two responsibilities:

1. `record_mentions()` — given chunks freshly upserted into Qdrant by
   the ingestion pipeline, extract entity references from each chunk's
   text and insert rows into Postgres `entity_mentions` (deduped by the
   table's UNIQUE constraint).

2. `find_synthesis_candidates()` — query Postgres for (entity, dept)
   pairs whose distinct-source-document count is at or above the
   per-dept threshold AND whose `synthesis_state.status` is
   `not_proposed`. The synthesis_proposer (separate module) reads this
   list, drafts a concept note, and writes a vault staging manifest via
   `services/shared/vault_staging.write_vault_staging`.

Entity extraction in this commit uses a deliberately conservative
heuristic: PascalCase tokens of length >= 2 words, plus a small allowlist
of single-word tokens (BICL, BNB, LCR, NSFR, CAR, RWA, etc.). This is
intentionally low-recall to avoid spamming the synthesis queue on day
one. The NER plug-in point is the `extract_entities()` function — swap
in spaCy `en_core_web_sm` (or a smaller transformer) by replacing the
body.

Hard rule: this module NEVER writes to the vault. It only inserts into
Postgres (Zone 2 metadata) and returns candidates. The synthesis_proposer
is responsible for vault staging manifests.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

THRESHOLDS_PATH_DEFAULT = "/app/config/synthesis_thresholds.json"

# Acronyms / known shorthand worth tracking despite being single tokens
ACRONYM_ALLOWLIST: frozenset[str] = frozenset({
    "BICL", "BNB", "LCR", "NSFR", "CAR", "RWA", "CET1", "EVE", "NII", "DSCR",
    "MTM", "DAT", "ESG", "OKR", "CFO", "CRO", "CIO", "CHRO", "CLO", "COO",
    "AML", "KYC", "SEC", "BOT", "MAS", "OECD", "IFRS", "GAAP",
})

# Match 2+ capitalized words separated by spaces (Audit Committee, Capital Allocation, ...)
PASCAL_RUN_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5})\b")
# Match acronyms (2-5 uppercase chars) — broader than allowlist; filtered downstream
ACRONYM_RE = re.compile(r"\b[A-Z]{2,5}\b")
# Tokens to drop after extraction
STOPWORDS: frozenset[str] = frozenset({
    "The", "A", "An", "And", "Or", "But", "For", "Of", "In", "On",
})


@dataclass(frozen=True)
class EntityMention:
    entity: str                  # canonical slug
    entity_display_name: str     # original casing
    entity_kind: str             # company|instrument|regulation|concept|person|other
    source_doc: str
    dept: str
    chunk_id: str | None = None


@dataclass(frozen=True)
class SynthesisCandidate:
    entity: str
    dept: str
    source_count: int
    threshold_used: int


def _slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name.strip().lower())
    return s.strip("-")


def _classify(token: str) -> str:
    """Best-effort entity-kind classification. Refine later."""
    if token in ACRONYM_ALLOWLIST:
        return "instrument" if token in {"BNB", "BICL"} else "concept"
    if re.search(r"\b(Committee|Council|Board|Department|Bank|Group|Company)\b", token):
        return "company"
    if re.search(r"\bSection\s+\d|\bRule\s+\d|Act\s+\d{4}", token):
        return "regulation"
    return "concept"


def extract_entities(text: str) -> set[tuple[str, str, str]]:
    """Return {(slug, display_name, entity_kind)} extracted from `text`.

    Conservative heuristic — see module docstring. Replace with NER for
    higher recall once we have the corpus to tune it on.
    """
    out: set[tuple[str, str, str]] = set()
    for match in PASCAL_RUN_RE.finditer(text):
        words = match.group(0).split()
        # Strip leading stopwords (e.g. "The Audit Committee" -> "Audit Committee")
        while words and words[0] in STOPWORDS:
            words = words[1:]
        if len(words) < 2:
            continue  # Need 2+ words for a multi-word entity
        token = " ".join(words)
        out.add((_slugify(token), token, _classify(token)))
    for match in ACRONYM_RE.finditer(text):
        token = match.group(0)
        if token in ACRONYM_ALLOWLIST:
            out.add((_slugify(token), token, _classify(token)))
    return out


def load_thresholds(path: str | Path = THRESHOLDS_PATH_DEFAULT) -> dict:
    """Load per-dept thresholds. Returns {"default": int, "per_dept": {dept: int}}."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.warning("synthesis_tracker: thresholds file unreadable (%s); using default=3", exc)
        return {"default": 3, "per_dept": {}}
    return {
        "default": int(data.get("default", 3)),
        "per_dept": {k: int(v) for k, v in data.get("per_dept", {}).items()},
    }


def threshold_for_dept(dept: str, thresholds: dict) -> int:
    return thresholds["per_dept"].get(dept, thresholds["default"])


async def record_mentions(
    pool,
    *,
    chunks: Iterable[dict],
    source_doc: str,
    dept: str,
) -> int:
    """Record entity mentions for each chunk. Returns count of rows inserted.

    `chunks` items must be dict-like with keys: `text` (str), optional `id` (str).
    Skips silently if the entity_mentions table doesn't exist (pre-migration state).
    """
    rows: list[tuple[str, str, str, str, str, str | None]] = []
    for chunk in chunks:
        chunk_id = chunk.get("id") if isinstance(chunk, dict) else None
        text = chunk["text"] if isinstance(chunk, dict) else getattr(chunk, "text", "")
        for slug, display, kind in extract_entities(text):
            rows.append((slug, display, kind, source_doc, dept, chunk_id))
    if not rows:
        return 0
    try:
        async with pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO entity_mentions
                   (entity, entity_display_name, entity_kind, source_doc, dept, chunk_id)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (entity, source_doc, chunk_id) DO NOTHING""",
                rows,
            )
    except Exception as exc:
        # Pre-bootstrap (migration not yet applied) is the most likely cause.
        # Diagnostic only — never let mention tracking break the ingest path.
        log.warning("synthesis_tracker.record_mentions skipped: %s", exc)
        return 0
    return len(rows)


async def find_synthesis_candidates(
    pool,
    *,
    thresholds: dict,
) -> list[SynthesisCandidate]:
    """Return entity/dept pairs above their per-dept threshold AND not yet proposed."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT em.entity, em.dept,
                          COUNT(DISTINCT em.source_doc) AS source_count
                   FROM entity_mentions em
                   LEFT JOIN synthesis_state ss
                     ON ss.entity = em.entity AND ss.dept = em.dept
                   WHERE ss.status IS NULL OR ss.status = 'not_proposed'
                   GROUP BY em.entity, em.dept"""
            )
    except Exception as exc:
        log.warning("synthesis_tracker.find_synthesis_candidates skipped: %s", exc)
        return []

    out: list[SynthesisCandidate] = []
    for r in rows:
        dept = r["dept"]
        n = int(r["source_count"])
        thresh = threshold_for_dept(dept, thresholds)
        if n >= thresh:
            out.append(SynthesisCandidate(
                entity=r["entity"], dept=dept,
                source_count=n, threshold_used=thresh,
            ))
    return out


async def mark_proposed(pool, *, entity: str, dept: str, proposal_id: str) -> None:
    """Mark a candidate as `proposed_pending` so we don't re-propose tomorrow."""
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO synthesis_state (entity, dept, status, proposal_id)
                   VALUES ($1, $2, 'proposed_pending', $3)
                   ON CONFLICT (entity, dept) DO UPDATE
                     SET status = 'proposed_pending',
                         proposal_id = EXCLUDED.proposal_id,
                         last_changed_at = NOW()""",
                entity, dept, proposal_id,
            )
    except Exception as exc:
        log.warning("synthesis_tracker.mark_proposed skipped: %s", exc)
