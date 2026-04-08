"""Generator for 'escalation' articles from escalation events."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..models import CompileEvent, WikiArticle
from ._common import parse_or_construct, slugify, today_iso

if TYPE_CHECKING:
    from ..compiler import WikiCompiler

_SYSTEM_PROMPT = """\
You are a professional knowledge-base writer for a financial institution.
Write a wiki article of type 'escalation' documenting a compliance or risk
threshold breach that required escalation.
The article MUST include the following Markdown sections in order:

- ## Summary
- ## Severity
- ## Trigger Details
- ## Resolution
- ## Follow-Up

Return the article as a Markdown file with YAML frontmatter delimited by ---.
The frontmatter must include: title, type, department, sources, related,
created, updated, confidence, coverage, tags, ticket_id.
Use ISO date format (YYYY-MM-DD) for date fields.
Be concise and precise about numeric thresholds and breach details.
"""


async def generate(event: CompileEvent, compiler: WikiCompiler) -> WikiArticle:
    """Generate an escalation article from an escalation event."""
    payload = event.payload
    today = today_iso()

    trigger: str = payload.get("trigger", "unknown-trigger")
    severity: str = payload.get("severity", "unknown")
    slug = slugify(trigger)
    file_path = f"{event.dept_id}/decisions/{today}-escalation-{slug}.md"

    notified: list[str] = payload.get("notified", [])

    user_prompt = (
        f"Department: {event.dept_id}\n"
        f"Date: {today}\n\n"
        f"Escalation details:\n{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )

    raw = await compiler._call_llm(_SYSTEM_PROMPT, user_prompt)

    # Map severity string to confidence: critical→high, warning→medium, else low
    _sev_map = {"critical": "high", "warning": "medium", "info": "low"}
    confidence = _sev_map.get(severity, "medium")  # type: ignore[assignment]

    title = f"Escalation — {trigger.replace('_', ' ').title()} ({severity})"

    return parse_or_construct(
        raw,
        file_path=file_path,
        title=title,
        article_type="escalation",
        department=event.dept_id,
        sources=notified,
        confidence=confidence,  # type: ignore[arg-type]
        tags=["escalation", severity, slug],
    )
