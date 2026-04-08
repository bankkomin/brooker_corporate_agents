"""Generator for 'entity' articles (facilities, instruments, people)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..models import CompileEvent, WikiArticle
from ._common import parse_or_construct, slugify, today_iso

if TYPE_CHECKING:
    from ..compiler import WikiCompiler

_SYSTEM_PROMPT = """\
You are a professional knowledge-base writer for a financial institution.
Write a wiki article of type 'entity' documenting a named entity such as
a credit facility, financial instrument, or key person.
The article MUST include the following Markdown sections in order:

- ## Overview
- ## Key Facts
- ## History
- ## Related Entities

Return the article as a Markdown file with YAML frontmatter delimited by ---.
The frontmatter must include: title, type, department, sources, related,
created, updated, confidence, coverage, tags, ticket_id.
Use ISO date format (YYYY-MM-DD) for date fields.
Be factual and structured.
"""


async def generate(event: CompileEvent, compiler: WikiCompiler) -> WikiArticle:
    """Generate an entity article for a facility, instrument, or person."""
    payload = event.payload
    today = today_iso()

    entity_name: str = payload.get("entity_name", "unknown-entity")
    entity_type: str = payload.get("entity_type", "entity")
    slug = slugify(entity_name)
    file_path = f"{event.dept_id}/entities/{slug}.md"

    sources: list[str] = list(payload.get("sources", []))

    user_prompt = (
        f"Department: {event.dept_id}\n"
        f"Date: {today}\n\n"
        f"Entity details:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )

    raw = await compiler._call_llm(_SYSTEM_PROMPT, user_prompt)

    return parse_or_construct(
        raw,
        file_path=file_path,
        title=entity_name,
        article_type="entity",
        department=event.dept_id,
        sources=sources,
        confidence="medium",
        tags=["entity", entity_type, slug],
    )
