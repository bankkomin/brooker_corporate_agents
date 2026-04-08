"""Generator for 'source-summary' articles from newly ingested documents."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..models import CompileEvent, WikiArticle
from ._common import parse_or_construct, slugify, today_iso

if TYPE_CHECKING:
    from ..compiler import WikiCompiler

_SYSTEM_PROMPT = """\
You are a professional knowledge-base writer for a financial institution.
Write a wiki article of type 'source-summary' for a newly ingested document.
The article MUST include the following Markdown sections in order:

- ## Document Overview
- ## Key Findings
- ## Relevance
- ## Extracted Data

Return the article as a Markdown file with YAML frontmatter delimited by ---.
The frontmatter must include: title, type, department, sources, related,
created, updated, confidence, coverage, tags, ticket_id.
Use ISO date format (YYYY-MM-DD) for date fields.
Be factual and structured. Note the document type and chunk count.
"""


async def generate(event: CompileEvent, compiler: WikiCompiler) -> WikiArticle:
    """Generate a source-summary article for a newly ingested document."""
    payload = event.payload
    today = today_iso()

    filename: str = payload.get("filename", "unknown-document")
    slug = slugify(filename)
    file_path = f"{event.dept_id}/concepts/source-{slug}.md"

    sources = [filename]

    user_prompt = (
        f"Department: {event.dept_id}\n"
        f"Date: {today}\n\n"
        f"Document ingestion details:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )

    raw = await compiler._call_llm(_SYSTEM_PROMPT, user_prompt)

    doc_type: str = payload.get("doc_type", "document")
    title = f"Source Summary — {filename}"

    return parse_or_construct(
        raw,
        file_path=file_path,
        title=title,
        article_type="source-summary",
        department=event.dept_id,
        sources=sources,
        confidence="medium",
        tags=["source-summary", doc_type, slug],
    )
