"""Tests for wiki-compiler Pydantic v2 models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from services.wiki_compiler.src.models import (
    ArticleFrontmatter,
    CompileEvent,
    CompileResponse,
    LintReport,
    LintResult,
    WikiArticle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_frontmatter(**overrides: object) -> ArticleFrontmatter:
    base = {
        "title": "Funding Rate Decision",
        "type": "decision",
        "department": "cac",
        "created": "2026-04-07",
        "updated": "2026-04-07",
        "confidence": "high",
    }
    base.update(overrides)
    return ArticleFrontmatter(**base)  # type: ignore[arg-type]


def make_article(**overrides: object) -> WikiArticle:
    fm = make_frontmatter()
    base = {
        "frontmatter": fm,
        "body": "## Summary\n\nThe committee approved a rate change.",
        "file_path": "cac/decisions/2026-04-07-funding-update.md",
    }
    base.update(overrides)
    return WikiArticle(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ArticleFrontmatter
# ---------------------------------------------------------------------------

class TestArticleFrontmatter:
    def test_required_fields_instantiate(self) -> None:
        fm = make_frontmatter()
        assert fm.title == "Funding Rate Decision"
        assert fm.type == "decision"
        assert fm.department == "cac"
        assert fm.confidence == "high"

    def test_optional_fields_default(self) -> None:
        fm = make_frontmatter()
        assert fm.sources == []
        assert fm.related == []
        assert fm.tags == []
        assert fm.ticket_id is None
        assert fm.coverage == "low"

    def test_optional_fields_populated(self) -> None:
        fm = make_frontmatter(
            sources=["#cac-committee", "ALCO_Tracker.xlsx"],
            related=["funding-policy.md"],
            tags=["alco", "funding"],
            ticket_id="chg_0042",
            coverage="medium",
        )
        assert fm.sources == ["#cac-committee", "ALCO_Tracker.xlsx"]
        assert fm.ticket_id == "chg_0042"
        assert fm.coverage == "medium"

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            ArticleFrontmatter(  # type: ignore[call-arg]
                type="decision",
                department="cac",
                created="2026-04-07",
                updated="2026-04-07",
                confidence="high",
                # title missing
            )

    def test_invalid_type_literal_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_frontmatter(type="unknown-type")

    def test_invalid_confidence_literal_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_frontmatter(confidence="very-high")

    def test_invalid_coverage_literal_raises(self) -> None:
        with pytest.raises(ValidationError):
            make_frontmatter(coverage="extreme")

    def test_all_type_literals_accepted(self) -> None:
        valid_types = [
            "concept",
            "decision",
            "meeting-note",
            "entity",
            "escalation",
            "source-summary",
            "trend",
        ]
        for t in valid_types:
            fm = make_frontmatter(type=t)
            assert fm.type == t


# ---------------------------------------------------------------------------
# WikiArticle
# ---------------------------------------------------------------------------

class TestWikiArticle:
    def test_instantiate(self) -> None:
        article = make_article()
        assert article.file_path == "cac/decisions/2026-04-07-funding-update.md"
        assert "committee" in article.body

    def test_to_markdown_contains_yaml_block(self) -> None:
        article = make_article()
        md = article.to_markdown()
        assert md.startswith("---\n")
        # second --- delimiter separates frontmatter from body
        parts = md.split("---\n", 2)
        assert len(parts) == 3, "Expected opening ---, YAML block, and body"

    def test_to_markdown_contains_title(self) -> None:
        article = make_article()
        md = article.to_markdown()
        assert "Funding Rate Decision" in md

    def test_to_markdown_contains_body(self) -> None:
        article = make_article()
        md = article.to_markdown()
        assert "## Summary" in md

    def test_from_markdown_roundtrip(self) -> None:
        original = make_article()
        md = original.to_markdown()
        restored = WikiArticle.from_markdown(md, original.file_path)

        assert restored.frontmatter.title == original.frontmatter.title
        assert restored.frontmatter.type == original.frontmatter.type
        assert restored.frontmatter.department == original.frontmatter.department
        assert restored.frontmatter.confidence == original.frontmatter.confidence
        assert restored.file_path == original.file_path
        assert "committee" in restored.body

    def test_from_markdown_roundtrip_with_optional_fields(self) -> None:
        original = make_article(
            frontmatter=make_frontmatter(
                sources=["#cac-committee"],
                tags=["alco"],
                ticket_id="chg_007",
                coverage="high",
            )
        )
        md = original.to_markdown()
        restored = WikiArticle.from_markdown(md, original.file_path)

        assert restored.frontmatter.sources == ["#cac-committee"]
        assert restored.frontmatter.tags == ["alco"]
        assert restored.frontmatter.ticket_id == "chg_007"
        assert restored.frontmatter.coverage == "high"


# ---------------------------------------------------------------------------
# CompileEvent
# ---------------------------------------------------------------------------

class TestCompileEvent:
    def test_instantiate(self) -> None:
        evt = CompileEvent(
            event_type="proposal_approved",
            dept_id="cac",
            payload={"change_id": "chg_0001"},
        )
        assert evt.event_type == "proposal_approved"
        assert evt.dept_id == "cac"
        assert evt.payload["change_id"] == "chg_0001"

    def test_default_timestamp_set(self) -> None:
        evt = CompileEvent(
            event_type="document_ingested",
            dept_id="cac",
            payload={},
        )
        assert evt.timestamp != ""
        # ISO datetime format sanity check
        assert "T" in evt.timestamp or "-" in evt.timestamp

    def test_source_id_optional(self) -> None:
        evt = CompileEvent(
            event_type="slack_digest",
            dept_id="cac",
            payload={},
        )
        assert evt.source_id is None

    def test_invalid_event_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            CompileEvent(
                event_type="invalid_event",  # type: ignore[arg-type]
                dept_id="cac",
                payload={},
            )

    def test_all_event_types_accepted(self) -> None:
        valid_types = [
            "proposal_approved",
            "document_ingested",
            "slack_digest",
            "escalation_triggered",
            "lint_request",
        ]
        for et in valid_types:
            evt = CompileEvent(event_type=et, dept_id="cac", payload={})  # type: ignore[arg-type]
            assert evt.event_type == et


# ---------------------------------------------------------------------------
# CompileResponse
# ---------------------------------------------------------------------------

class TestCompileResponse:
    def test_compiled_status(self) -> None:
        r = CompileResponse(
            status="compiled",
            article_path="cac/decisions/2026-04-07-test.md",
            pages_updated=["cac/decisions/2026-04-07-test.md"],
        )
        assert r.status == "compiled"
        assert r.pages_updated == ["cac/decisions/2026-04-07-test.md"]

    def test_skipped_defaults(self) -> None:
        r = CompileResponse(status="skipped", reason="No new content")
        assert r.article_path == ""
        assert r.pages_updated == []
        assert r.reason == "No new content"

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            CompileResponse(status="pending")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# LintResult
# ---------------------------------------------------------------------------

class TestLintResult:
    def test_instantiate(self) -> None:
        lr = LintResult(
            issue_type="contradiction",
            article_path="cac/decisions/old.md",
            description="Contradicts funding policy in source-summary.md",
            severity="critical",
        )
        assert lr.issue_type == "contradiction"
        assert lr.severity == "critical"
        assert lr.suggested_action == ""

    def test_with_suggested_action(self) -> None:
        lr = LintResult(
            issue_type="stale",
            article_path="cac/concepts/liquidity.md",
            description="Last updated 90 days ago",
            severity="warning",
            suggested_action="Re-run ingestion for related Slack thread",
        )
        assert lr.suggested_action != ""

    def test_invalid_issue_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            LintResult(
                issue_type="typo",  # type: ignore[arg-type]
                article_path="x.md",
                description="desc",
                severity="info",
            )

    def test_invalid_severity_raises(self) -> None:
        with pytest.raises(ValidationError):
            LintResult(
                issue_type="orphan",
                article_path="x.md",
                description="desc",
                severity="high",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# LintReport
# ---------------------------------------------------------------------------

class TestLintReport:
    def _make_result(self, issue_type: str = "orphan") -> LintResult:
        return LintResult(
            issue_type=issue_type,  # type: ignore[arg-type]
            article_path="cac/orphan.md",
            description="No incoming links",
            severity="info",
        )

    def test_issues_found_computed(self) -> None:
        results = [self._make_result(), self._make_result("stale")]
        report = LintReport(
            dept_id="cac",
            timestamp="2026-04-07T12:00:00",
            results=results,
            articles_scanned=10,
        )
        assert report.issues_found == 2

    def test_zero_issues(self) -> None:
        report = LintReport(
            dept_id="cac",
            timestamp="2026-04-07T12:00:00",
            results=[],
            articles_scanned=5,
        )
        assert report.issues_found == 0

    def test_missing_dept_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            LintReport(  # type: ignore[call-arg]
                timestamp="2026-04-07T12:00:00",
                results=[],
                articles_scanned=0,
            )
