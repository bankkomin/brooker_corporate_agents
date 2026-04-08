"""Generator for 'concept' articles from multi-source topics."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..models import CompileEvent, WikiArticle
from ._common import parse_or_construct, slugify, today_iso

if TYPE_CHECKING:
    from ..compiler import WikiCompiler

_SYSTEM_PROMPT = """\
You are a professional knowledge-base writer for a financial institution.
Write a wiki article of type 'concept' explaining a financial or technical topic.
The article MUST include the following Markdown sections in order:

- ## Summary
- ## Key Metrics
- ## Historical Context
- ## Related Concepts
- ## Sources

Return the article as a Markdown file with YAML frontmatter delimited by ---.
The frontmatter must include: title, type, department, sources, related,
created, updated, confidence, coverage, tags, ticket_id.
Use ISO date format (YYYY-MM-DD) for date fields.
Be educational, concise, and citation-driven.
"""


async def generate(event: CompileEvent, compiler: WikiCompiler) -> WikiArticle:
    """Generate a concept article from a multi-source topic event."""
    payload = event.payload
    today = today_iso()

    topic: str = payload.get("topic", "unknown-topic")
    slug = slugify(topic)
    file_path = f"{event.dept_id}/concepts/{slug}.md"

    sources: list[str] = list(payload.get("sources", []))

    user_prompt = (
        f"Department: {event.dept_id}\n"
        f"Date: {today}\n\n"
        f"Concept details:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )

    raw = await compiler._call_llm(_SYSTEM_PROMPT, user_prompt)

    return parse_or_construct(
        raw,
        file_path=file_path,
        title=topic,
        article_type="concept",
        department=event.dept_id,
        sources=sources,
        confidence="medium",
        tags=["concept", slug],
    )
