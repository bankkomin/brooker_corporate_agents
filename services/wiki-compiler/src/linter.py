"""Wiki health checker — finds contradictions, stale data, orphans, and coverage gaps."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import structlog

from .linker import Linker
from .models import LintReport, LintResult, WikiArticle

logger = structlog.get_logger("wiki-compiler.linter")

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Files that live at the department root and are never subject to lint checks.
_RESERVED_FILENAMES = {"index.md", "log.md", "lint-report.md"}


class WikiLinter:
    """Performs periodic health checks on a department's wiki vault.

    Checks performed:
    - stale: articles not updated within *threshold_days*
    - orphan: articles with no inbound [[wikilinks]] from other articles
    - missing_concept: [[wikilinks]] that resolve to no file on disk
    - broken_link: same as missing_concept (delegated to Linker)
    - low_coverage: articles with fewer than 2 source entries
    - contradiction: deferred to maintenance agent (requires LLM)
    """

    def __init__(self, vault_path: Path, linker: Linker) -> None:
        self._vault = vault_path
        self._linker = linker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lint_department(self, dept_id: str) -> LintReport:
        """Run all checks on *dept_id* and return an aggregated :class:`LintReport`.

        Scans every ``.md`` file in ``{vault_path}/{dept_id}/`` (excluding
        ``index.md``, ``log.md``, and ``lint-report.md``).
        """
        articles = self._scan_articles(dept_id)

        results: list[LintResult] = []
        results.extend(self._check_stale(articles))
        results.extend(self._check_orphans(articles))
        results.extend(self._check_missing_concepts(articles, dept_id))
        results.extend(self._score_coverage(articles))
        results.extend(self._check_contradictions(articles))

        return LintReport(
            dept_id=dept_id,
            timestamp=datetime.now(tz=UTC).isoformat(),
            results=results,
            articles_scanned=len(articles),
        )

    def write_lint_report(self, dept_id: str, report: LintReport) -> Path:
        """Write a human-readable ``lint-report.md`` to the department vault directory.

        Returns the :class:`Path` of the written file.
        """
        dept_dir = self._vault / dept_id
        dept_dir.mkdir(parents=True, exist_ok=True)
        report_path = dept_dir / "lint-report.md"

        generated_date = report.timestamp[:10]  # YYYY-MM-DD

        # Group results by severity
        by_severity: dict[str, list[LintResult]] = {
            "critical": [],
            "warning": [],
            "info": [],
        }
        for r in report.results:
            by_severity[r.severity].append(r)

        lines: list[str] = [
            "---",
            f"title: Lint Report \u2014 {dept_id.upper()}",
            "type: lint-report",
            f"department: {dept_id}",
            f"generated: {generated_date}",
            "---",
            "",
            f"# Lint Report \u2014 {dept_id.upper()}",
            "",
            f"**Generated:** {generated_date}",
            f"**Articles scanned:** {report.articles_scanned}",
            f"**Issues found:** {report.issues_found}",
            "",
        ]

        for severity in ("critical", "warning", "info"):
            lines.append(f"## {severity.capitalize()}")
            bucket = by_severity[severity]
            if not bucket:
                lines.append("(none)")
            else:
                for r in bucket:
                    if r.article_path:
                        lines.append(
                            f"- **{r.issue_type}** `{r.article_path}` \u2014 {r.description}"
                        )
                    else:
                        lines.append(f"- **{r.issue_type}** \u2014 {r.description}")
            lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(
            "linter.report_written",
            dept_id=dept_id,
            path=str(report_path),
            issues=report.issues_found,
        )
        return report_path

    # ------------------------------------------------------------------
    # Private checks
    # ------------------------------------------------------------------

    def _scan_articles(self, dept_id: str) -> list[WikiArticle]:
        """Read and parse all non-reserved ``.md`` files in the department vault."""
        dept_dir = self._vault / dept_id
        if not dept_dir.exists():
            logger.warning("linter.dept_dir_missing", dept_id=dept_id, path=str(dept_dir))
            return []

        articles: list[WikiArticle] = []
        for md_file in sorted(dept_dir.rglob("*.md")):
            if md_file.name in _RESERVED_FILENAMES:
                continue
            try:
                text = md_file.read_text(encoding="utf-8")
                rel_path = str(md_file.relative_to(self._vault))
                article = WikiArticle.from_markdown(text, file_path=rel_path)
                articles.append(article)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "linter.parse_failed",
                    file=str(md_file),
                    error=str(exc),
                )
        return articles

    def _check_stale(
        self, articles: list[WikiArticle], threshold_days: int = 30
    ) -> list[LintResult]:
        """Flag articles whose ``updated`` date is older than *threshold_days*."""
        now = datetime.now(tz=UTC)
        results: list[LintResult] = []

        for article in articles:
            try:
                updated_dt = datetime.fromisoformat(article.frontmatter.updated).replace(
                    tzinfo=UTC
                )
            except ValueError:
                logger.warning(
                    "linter.stale_check.bad_date",
                    path=article.file_path,
                    updated=article.frontmatter.updated,
                )
                continue

            age_days = (now - updated_dt).days
            if age_days > threshold_days:
                results.append(
                    LintResult(
                        issue_type="stale",
                        article_path=article.file_path,
                        description=(
                            f"Article not updated in {age_days} days"
                            f" (last updated: {article.frontmatter.updated})"
                        ),
                        severity="warning",
                        suggested_action="Review and update article content.",
                    )
                )

        return results

    def _check_orphans(self, articles: list[WikiArticle]) -> list[LintResult]:
        """Flag articles that no other article links to via ``[[wikilinks]]``."""
        # Collect every page stem referenced anywhere in the corpus
        referenced: set[str] = set()
        for article in articles:
            for ref in _WIKILINK_RE.findall(article.body):
                referenced.add(ref.lower())

        results: list[LintResult] = []
        for article in articles:
            stem = Path(article.file_path).stem.lower()
            if stem not in referenced:
                results.append(
                    LintResult(
                        issue_type="orphan",
                        article_path=article.file_path,
                        description="No inbound links from other articles",
                        severity="info",
                        suggested_action=(
                            "Add a [[wikilink]] to this article from a related page,"
                            " or remove if content is superseded."
                        ),
                    )
                )

        return results

    def _check_missing_concepts(
        self, articles: list[WikiArticle], dept_id: str  # noqa: ARG002
    ) -> list[LintResult]:
        """Flag ``[[wikilinks]]`` that have no corresponding file on disk."""
        broken = self._linker.find_broken_links(dept_id)
        results: list[LintResult] = []
        for ref in broken:
            results.append(
                LintResult(
                    issue_type="missing_concept",
                    article_path="",
                    description=f"Referenced [[{ref}]] has no matching file",
                    severity="warning",
                    suggested_action=(
                        f"Create a stub article for '{ref}' or correct the wikilink."
                    ),
                )
            )
        return results

    def _check_broken_links(self, dept_id: str) -> list[LintResult]:
        """Delegate broken-link detection to :class:`Linker`.

        This method exists as a named entry point for callers that want only
        broken-link results; internally it mirrors :meth:`_check_missing_concepts`.
        """
        broken = self._linker.find_broken_links(dept_id)
        results: list[LintResult] = []
        for ref in broken:
            results.append(
                LintResult(
                    issue_type="broken_link",
                    article_path="",
                    description=f"Wikilink [[{ref}]] resolves to no file",
                    severity="warning",
                    suggested_action=(
                        f"Create a page for '{ref}' or remove the dead link."
                    ),
                )
            )
        return results

    def _score_coverage(self, articles: list[WikiArticle]) -> list[LintResult]:
        """Flag articles that have fewer than 2 source citations."""
        results: list[LintResult] = []
        for article in articles:
            source_count = len(article.frontmatter.sources)
            if source_count < 2:
                results.append(
                    LintResult(
                        issue_type="low_coverage",
                        article_path=article.file_path,
                        description=(
                            f"Only {source_count} source"
                            + ("" if source_count == 1 else "s")
                        ),
                        severity="info",
                        suggested_action=(
                            "Add at least one more source citation to strengthen coverage."
                        ),
                    )
                )
        return results

    def _check_contradictions(self, articles: list[WikiArticle]) -> list[LintResult]:
        """Contradiction detection requires LLM analysis — deferred to maintenance agent."""
        logger.debug("linter.contradiction_check_deferred", reason="requires LLM")
        return []
