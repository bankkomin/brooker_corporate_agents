"""Shared helpers used by all article generators."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..models import ArticleFrontmatter, ConfidenceLevel, WikiArticle

if TYPE_CHECKING:
    pass


def slugify(text: str) -> str:
    """Convert arbitrary text to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def today_iso() -> str:
    """Return today's date as an ISO string (YYYY-MM-DD)."""
    return datetime.now(tz=UTC).date().isoformat()


def confidence_from_float(value: float | None) -> ConfidenceLevel:
    """Map a 0-1 float confidence to high/medium/low."""
    if value is None:
        return "medium"
    if value >= 0.85:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def parse_or_construct(
    raw: str,
    file_path: str,
    *,
    title: str,
    article_type: str,
    department: str,
    sources: list[str],
    confidence: ConfidenceLevel,
    tags: list[str] | None = None,
    ticket_id: str | None = None,
) -> WikiArticle:
    """Parse an LLM response into a WikiArticle.

    If the response contains ``---`` frontmatter delimiters, use
    :meth:`WikiArticle.from_markdown`.  Otherwise, construct the frontmatter
    from the supplied parameters and treat the entire raw string as the body.
    """

    today = today_iso()

    if raw.strip().startswith("---"):
        try:
            return WikiArticle.from_markdown(raw, file_path=file_path)
        except (ValueError, KeyError):
            pass  # fall through to manual construction

    fm = ArticleFrontmatter(
        title=title,
        type=article_type,  # type: ignore[arg-type]
        department=department,
        sources=sources,
        related=[],
        created=today,
        updated=today,
        confidence=confidence,
        coverage="low",
        tags=tags or [],
        ticket_id=ticket_id,
    )
    return WikiArticle(frontmatter=fm, body=raw, file_path=file_path)
