"""Generator for 'meeting-note' articles from Slack thread digests."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..models import CompileEvent, WikiArticle
from ._common import parse_or_construct, slugify, today_iso

if TYPE_CHECKING:
    from ..compiler import WikiCompiler

_SYSTEM_PROMPT = """\
You are a professional knowledge-base writer for a financial institution.
Write a wiki article of type 'meeting-note' summarising a Slack channel digest.
The article MUST include the following Markdown sections in order:

- ## Attendees
- ## Topics Discussed
- ## Decisions Made
- ## Action Items
- ## Follow-Up

Return the article as a Markdown file with YAML frontmatter delimited by ---.
The frontmatter must include: title, type, department, sources, related,
created, updated, confidence, coverage, tags, ticket_id.
Use ISO date format (YYYY-MM-DD) for date fields.
List each attendee as a bullet point under ## Attendees.
Be concise and factual.
"""


async def generate(event: CompileEvent, compiler: WikiCompiler) -> WikiArticle:
    """Generate a meeting-note article from a Slack digest event."""
    payload = event.payload
    # Use the date from the payload if present, otherwise fall back to today
    date = payload.get("date") or today_iso()
    channel = payload.get("channel", event.dept_id)
    slug = slugify(channel)
    file_path = f"{event.dept_id}/meeting-notes/{date}-{slug}.md"

    participants: list[str] = payload.get("participants", [])
    sources = [channel] if channel else []

    user_prompt = (
        f"Department: {event.dept_id}\n"
        f"Date: {date}\n"
        f"Channel: {channel}\n"
        f"Participants: {', '.join(participants)}\n\n"
        f"Digest details:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )

    raw = await compiler._call_llm(_SYSTEM_PROMPT, user_prompt)

    title = f"{event.dept_id.upper()} Meeting Notes — {date}"

    return parse_or_construct(
        raw,
        file_path=file_path,
        title=title,
        article_type="meeting-note",
        department=event.dept_id,
        sources=sources,
        confidence="medium",
        tags=["meeting", event.dept_id],
    )
