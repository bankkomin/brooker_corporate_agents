"""Pydantic v2 request/response schemas for wiki-compiler service."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import yaml
from pydantic import BaseModel, Field, computed_field

# ---------------------------------------------------------------------------
# ArticleFrontmatter
# ---------------------------------------------------------------------------

ArticleType = Literal[
    "concept",
    "decision",
    "meeting-note",
    "entity",
    "escalation",
    "source-summary",
    "trend",
]

ConfidenceLevel = Literal["high", "medium", "low"]
CoverageLevel = Literal["high", "medium", "low"]


class ArticleFrontmatter(BaseModel):
    """YAML frontmatter metadata for a compiled wiki article."""

    title: str
    type: ArticleType
    department: str
    sources: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    created: str = Field(..., description="ISO date string, e.g. 2026-04-07")
    updated: str = Field(..., description="ISO date string, e.g. 2026-04-07")
    confidence: ConfidenceLevel
    coverage: CoverageLevel = "low"
    tags: list[str] = Field(default_factory=list)
    ticket_id: str | None = None


# ---------------------------------------------------------------------------
# WikiArticle
# ---------------------------------------------------------------------------

class WikiArticle(BaseModel):
    """A compiled wiki article with frontmatter and markdown body."""

    frontmatter: ArticleFrontmatter
    body: str = Field(..., description="Markdown body content")
    file_path: str = Field(
        ..., description="Relative path within vault, e.g. cac/decisions/2026-04-07-funding.md"
    )

    def to_markdown(self) -> str:
        """Render the article as a Markdown file with YAML frontmatter."""
        fm_dict = self.frontmatter.model_dump()
        yaml_str = yaml.dump(fm_dict, default_flow_style=False, allow_unicode=True)
        return f"---\n{yaml_str}---\n\n{self.body}"

    @classmethod
    def from_markdown(cls, text: str, file_path: str) -> WikiArticle:
        """Parse a Markdown string with YAML frontmatter into a WikiArticle."""
        # Split on the --- delimiters.  Expect: '' | yaml_block | body
        parts = text.split("---\n", 2)
        if len(parts) != 3:
            raise ValueError(
                "Invalid wiki article format: expected YAML frontmatter delimited by ---"
            )
        _, yaml_block, body = parts
        fm_data = yaml.safe_load(yaml_block)
        frontmatter = ArticleFrontmatter(**fm_data)
        return cls(frontmatter=frontmatter, body=body.lstrip("\n"), file_path=file_path)


# ---------------------------------------------------------------------------
# CompileEvent
# ---------------------------------------------------------------------------

CompileEventType = Literal[
    "proposal_approved",
    "document_ingested",
    "slack_digest",
    "escalation_triggered",
    "lint_request",
]


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class CompileEvent(BaseModel):
    """Event that triggers wiki compilation."""

    event_type: CompileEventType
    dept_id: str
    payload: dict
    timestamp: str = Field(default_factory=_now_iso)
    source_id: str | None = Field(
        default=None, description="Paperclip ticket ID if applicable"
    )


# ---------------------------------------------------------------------------
# CompileResponse
# ---------------------------------------------------------------------------

CompileStatus = Literal["compiled", "skipped", "error"]


class CompileResponse(BaseModel):
    """Response returned by the /compile endpoint."""

    status: CompileStatus
    article_path: str = ""
    pages_updated: list[str] = Field(default_factory=list)
    reason: str = ""


# ---------------------------------------------------------------------------
# LintResult
# ---------------------------------------------------------------------------

LintIssueType = Literal[
    "contradiction",
    "stale",
    "orphan",
    "missing_concept",
    "broken_link",
    "low_coverage",
]

LintSeverity = Literal["critical", "warning", "info"]


class LintResult(BaseModel):
    """A single lint finding from the wiki consistency checker."""

    issue_type: LintIssueType
    article_path: str
    description: str
    severity: LintSeverity
    suggested_action: str = ""


# ---------------------------------------------------------------------------
# LintReport
# ---------------------------------------------------------------------------

class LintReport(BaseModel):
    """Aggregated lint report for a department's wiki."""

    dept_id: str
    timestamp: str
    results: list[LintResult]
    articles_scanned: int

    @computed_field  # type: ignore[misc]
    @property
    def issues_found(self) -> int:
        """Computed count of lint findings."""
        return len(self.results)
