"""Generator for 'decision' articles from approved staging proposals."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..models import CompileEvent, WikiArticle
from ._common import confidence_from_float, parse_or_construct, slugify, today_iso

if TYPE_CHECKING:
    from ..compiler import WikiCompiler

_SYSTEM_PROMPT = """\
You are a professional knowledge-base writer for a financial institution.
Write a wiki article of type 'decision' documenting an approved data change.
The article MUST include the following Markdown sections in order:

- ## Summary
- ## Change Details
- ## Rationale
- ## Source Evidence
- ## Impact

Return the article as a Markdown file with YAML frontmatter delimited by ---.
The frontmatter must include: title, type, department, sources, related,
created, updated, confidence, coverage, tags, ticket_id.
Use ISO date format (YYYY-MM-DD) for date fields.
Be concise, factual, and citation-driven.
"""


async def generate(event: CompileEvent, compiler: WikiCompiler) -> WikiArticle:
    """Generate a decision article from an approved staging proposal event."""
    payload = event.payload
    today = today_iso()

    # Derive a slug from the tab + cell (e.g. "funding-facilities-e8")
    tab = payload.get("tab", "unknown-tab")
    cell = payload.get("cell", "")
    raw_slug = f"{tab}-{cell}" if cell else tab
    slug = slugify(raw_slug)
    file_path = f"{event.dept_id}/decisions/{today}-{slug}.md"

    # Build user prompt with the full proposal detail
    user_prompt = (
        f"Department: {event.dept_id}\n"
        f"Date: {today}\n\n"
        f"Approved proposal details:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )

    raw = await compiler._call_llm(_SYSTEM_PROMPT, user_prompt)

    confidence = confidence_from_float(payload.get("confidence"))
    sources: list[str] = []
    if payload.get("source"):
        sources.append(str(payload["source"]))

    title = (
        f"Decision — {tab} {cell} Update"
        if cell
        else f"Decision — {tab} Update"
    )

    return parse_or_construct(
        raw,
        file_path=file_path,
        title=title,
        article_type="decision",
        department=event.dept_id,
        sources=sources,
        confidence=confidence,
        tags=["decision", slugify(tab)],
        ticket_id=payload.get("proposal_id"),
    )
