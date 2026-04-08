"""Tests for wiki-compiler WikiLinter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from services.wiki_compiler.src.linker import Linker
from services.wiki_compiler.src.linter import WikiLinter
from services.wiki_compiler.src.models import ArticleFrontmatter, LintReport, WikiArticle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_article(
    path: Path,
    title: str = "Test Article",
    article_type: str = "concept",
    dept: str = "cac",
    body: str = "Some body.",
    sources: list[str] | None = None,
    updated: str = "2026-04-07",
    related: list[str] | None = None,
) -> WikiArticle:
    """Write a WikiArticle to disk and return it."""
    fm = ArticleFrontmatter(
        title=title,
        type=article_type,  # type: ignore[arg-type]
        department=dept,
        sources=sources or [],
        related=related or [],
        created="2026-04-01",
        updated=updated,
        confidence="medium",
    )
    article = WikiArticle(
        frontmatter=fm,
        body=body,
        file_path=str(path.relative_to(path.parents[3])) if path.parents else str(path),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(article.to_markdown(), encoding="utf-8")
    return article


def make_linter(vault_path: Path, broken_links: list[str] | None = None) -> WikiLinter:
    """Create a WikiLinter with a mocked Linker."""
    mock_linker = MagicMock(spec=Linker)
    mock_linker.find_broken_links.return_value = broken_links or []
    return WikiLinter(vault_path=vault_path, linker=mock_linker)


# ---------------------------------------------------------------------------
# TestScanArticles
# ---------------------------------------------------------------------------


class TestScanArticles:
    def test_scan_articles_reads_all_md_files(self, tmp_path: Path) -> None:
        """_scan_articles returns one WikiArticle per .md file in the dept vault."""
        dept_dir = tmp_path / "cac"
        write_article(dept_dir / "concepts" / "lcr.md", title="LCR")
        write_article(dept_dir / "concepts" / "nsfr.md", title="NSFR")
        write_article(dept_dir / "entities" / "bbk.md", title="BBK")

        linter = make_linter(tmp_path)
        articles = linter._scan_articles("cac")

        assert len(articles) == 3
        titles = {a.frontmatter.title for a in articles}
        assert titles == {"LCR", "NSFR", "BBK"}

    def test_scan_articles_skips_reserved_files(self, tmp_path: Path) -> None:
        """_scan_articles excludes index.md, log.md, and lint-report.md."""
        dept_dir = tmp_path / "cac"
        write_article(dept_dir / "concepts" / "lcr.md", title="LCR")

        # Write reserved files directly (they may not have valid frontmatter)
        (dept_dir / "index.md").write_text("# Index\n", encoding="utf-8")
        (dept_dir / "log.md").write_text("# Log\n", encoding="utf-8")
        (dept_dir / "lint-report.md").write_text("# Lint\n", encoding="utf-8")

        linter = make_linter(tmp_path)
        articles = linter._scan_articles("cac")

        assert len(articles) == 1
        assert articles[0].frontmatter.title == "LCR"


# ---------------------------------------------------------------------------
# TestCheckStale
# ---------------------------------------------------------------------------


class TestCheckStale:
    def test_check_stale_detects_old_article(self, tmp_path: Path) -> None:
        """_check_stale returns a LintResult for articles older than threshold."""
        dept_dir = tmp_path / "cac"
        write_article(
            dept_dir / "concepts" / "lcr.md",
            title="LCR",
            updated="2025-01-01",  # well over 30 days ago
        )

        linter = make_linter(tmp_path)
        articles = [WikiArticle.from_markdown(
            (dept_dir / "concepts" / "lcr.md").read_text(encoding="utf-8"),
            file_path="cac/concepts/lcr.md",
        )]
        results = linter._check_stale(articles, threshold_days=30)

        assert len(results) == 1
        assert results[0].issue_type == "stale"
        assert results[0].severity == "warning"
        assert "lcr" in results[0].article_path

    def test_check_stale_passes_recent_article(self, tmp_path: Path) -> None:
        """_check_stale does not flag articles updated recently."""
        dept_dir = tmp_path / "cac"
        write_article(
            dept_dir / "concepts" / "lcr.md",
            title="LCR",
            updated="2026-04-07",  # today's date in test context
        )

        linter = make_linter(tmp_path)
        articles = [WikiArticle.from_markdown(
            (dept_dir / "concepts" / "lcr.md").read_text(encoding="utf-8"),
            file_path="cac/concepts/lcr.md",
        )]
        results = linter._check_stale(articles, threshold_days=30)

        assert results == []


# ---------------------------------------------------------------------------
# TestCheckOrphans
# ---------------------------------------------------------------------------


class TestCheckOrphans:
    def test_check_orphans_detects_unreferenced_article(self, tmp_path: Path) -> None:
        """_check_orphans returns a LintResult for articles with no inbound links."""
        dept_dir = tmp_path / "cac"
        write_article(dept_dir / "concepts" / "lcr.md", title="LCR", body="No links here.")
        write_article(
            dept_dir / "concepts" / "nsfr.md",
            title="NSFR",
            body="See [[lcr]] for details.",  # nsfr links to lcr, not to bbk
        )
        write_article(dept_dir / "entities" / "bbk.md", title="BBK", body="Standalone.")

        linter = make_linter(tmp_path)
        articles = [
            WikiArticle.from_markdown(
                p.read_text(encoding="utf-8"), file_path=str(p.relative_to(tmp_path))
            )
            for p in [
                dept_dir / "concepts" / "lcr.md",
                dept_dir / "concepts" / "nsfr.md",
                dept_dir / "entities" / "bbk.md",
            ]
        ]
        results = linter._check_orphans(articles)

        orphan_paths = {r.article_path for r in results}
        # nsfr and bbk are not referenced by anyone; lcr is referenced by nsfr
        assert any("nsfr" in p for p in orphan_paths)
        assert any("bbk" in p for p in orphan_paths)
        assert not any("lcr" in p for p in orphan_paths)
        assert all(r.issue_type == "orphan" for r in results)
        assert all(r.severity == "info" for r in results)


# ---------------------------------------------------------------------------
# TestCheckMissingConcepts
# ---------------------------------------------------------------------------


class TestCheckMissingConcepts:
    def test_check_missing_concepts_detects_broken_links(self, tmp_path: Path) -> None:
        """_check_missing_concepts returns LintResults for unresolved [[links]]."""
        mock_linker = MagicMock(spec=Linker)
        mock_linker.find_broken_links.return_value = ["duration-gap", "basel-iv"]

        linter = WikiLinter(vault_path=tmp_path, linker=mock_linker)
        dept_dir = tmp_path / "cac"
        write_article(dept_dir / "concepts" / "lcr.md", title="LCR")
        articles = [WikiArticle.from_markdown(
            (dept_dir / "concepts" / "lcr.md").read_text(encoding="utf-8"),
            file_path="cac/concepts/lcr.md",
        )]

        results = linter._check_missing_concepts(articles, dept_id="cac")

        assert len(results) == 2
        descriptions = " ".join(r.description for r in results)
        assert "duration-gap" in descriptions
        assert "basel-iv" in descriptions
        assert all(r.issue_type == "missing_concept" for r in results)
        assert all(r.severity == "warning" for r in results)


# ---------------------------------------------------------------------------
# TestScoreCoverage
# ---------------------------------------------------------------------------


class TestScoreCoverage:
    def test_score_coverage_flags_articles_with_fewer_than_two_sources(
        self, tmp_path: Path
    ) -> None:
        """_score_coverage returns LintResult for articles with < 2 sources."""
        dept_dir = tmp_path / "cac"
        write_article(
            dept_dir / "concepts" / "lcr.md",
            title="LCR",
            sources=["Slack #cac 2026-04-01"],  # only 1 source
        )
        write_article(
            dept_dir / "concepts" / "nsfr.md",
            title="NSFR",
            sources=["Slack #cac 2026-04-01", "ALCO_Tracker.xlsx"],  # 2 sources — OK
        )

        linter = make_linter(tmp_path)
        articles = [
            WikiArticle.from_markdown(
                p.read_text(encoding="utf-8"), file_path=str(p.relative_to(tmp_path))
            )
            for p in [
                dept_dir / "concepts" / "lcr.md",
                dept_dir / "concepts" / "nsfr.md",
            ]
        ]
        results = linter._score_coverage(articles)

        assert len(results) == 1
        assert "lcr" in results[0].article_path
        assert results[0].issue_type == "low_coverage"
        assert results[0].severity == "info"


# ---------------------------------------------------------------------------
# TestWriteLintReport
# ---------------------------------------------------------------------------


class TestWriteLintReport:
    def test_write_lint_report_creates_markdown_file(self, tmp_path: Path) -> None:
        """write_lint_report writes a lint-report.md file to the dept vault dir."""
        dept_dir = tmp_path / "cac"
        dept_dir.mkdir(parents=True)

        linter = make_linter(tmp_path)
        report = LintReport(
            dept_id="cac",
            timestamp="2026-04-07T00:00:00+00:00",
            results=[],
            articles_scanned=5,
        )
        report_path = linter.write_lint_report("cac", report)

        assert report_path == dept_dir / "lint-report.md"
        assert report_path.exists()

        content = report_path.read_text(encoding="utf-8")
        assert "Lint Report" in content
        assert "Articles scanned" in content
        assert "5" in content


# ---------------------------------------------------------------------------
# TestLintDepartment
# ---------------------------------------------------------------------------


class TestLintDepartment:
    def test_lint_department_aggregates_all_checks(self, tmp_path: Path) -> None:
        """lint_department runs all checks and returns a LintReport."""
        dept_dir = tmp_path / "cac"

        # stale article
        write_article(
            dept_dir / "concepts" / "lcr.md",
            title="LCR",
            updated="2025-01-01",
            sources=["one-source"],  # also low coverage
            body="No outbound links.",
        )
        # recent article with 2 sources, links to lcr
        write_article(
            dept_dir / "concepts" / "nsfr.md",
            title="NSFR",
            updated="2026-04-07",
            sources=["Slack #cac", "ALCO tracker"],
            body="See [[lcr]] for details.",
        )

        mock_linker = MagicMock(spec=Linker)
        mock_linker.find_broken_links.return_value = []
        linter = WikiLinter(vault_path=tmp_path, linker=mock_linker)

        report = linter.lint_department("cac")

        assert isinstance(report, LintReport)
        assert report.dept_id == "cac"
        assert report.articles_scanned == 2
        assert report.issues_found > 0

        issue_types = {r.issue_type for r in report.results}
        # lcr is stale (updated 2025-01-01)
        assert "stale" in issue_types
        # lcr has only 1 source
        assert "low_coverage" in issue_types
        # nsfr and lcr: nsfr links to lcr, lcr and nsfr themselves have no inbound links
        # at least one orphan expected (nsfr has no inbound link)
        assert "orphan" in issue_types
