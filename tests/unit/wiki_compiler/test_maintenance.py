"""Tests for wiki-compiler MaintenanceAgent."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from services.wiki_compiler.src.index_manager import IndexManager
from services.wiki_compiler.src.linter import WikiLinter
from services.wiki_compiler.src.log_writer import LogWriter
from services.wiki_compiler.src.maintenance_agent import MaintenanceAgent
from services.wiki_compiler.src.models import ArticleFrontmatter, LintReport, WikiArticle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(
    tmp_path: Path,
) -> tuple[MaintenanceAgent, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return a MaintenanceAgent wired with mocked dependencies."""
    from services.wiki_compiler.src.config import WikiSettings

    settings = WikiSettings(vault_path=str(tmp_path), paperclip_url="http://paperclip:3100")

    mock_linter = MagicMock(spec=WikiLinter)
    mock_linter.lint_department.return_value = LintReport(
        dept_id="cac",
        timestamp="2026-04-07T00:00:00+00:00",
        results=[],
        articles_scanned=0,
    )
    mock_linter.write_lint_report.return_value = tmp_path / "cac" / "lint-report.md"

    mock_log_writer = MagicMock(spec=LogWriter)
    mock_index_manager = MagicMock(spec=IndexManager)

    mock_dept_router = MagicMock()
    mock_dept_router.list_departments.return_value = ["cac", "hr"]

    agent = MaintenanceAgent(
        settings=settings,
        linter=mock_linter,
        log_writer=mock_log_writer,
        index_manager=mock_index_manager,
        dept_router=mock_dept_router,
    )
    return agent, mock_linter, mock_log_writer, mock_index_manager, mock_dept_router


def _write_article(
    path: Path,
    updated: str = "2026-04-07",
) -> None:
    """Write a minimal valid wiki article to disk."""
    fm = ArticleFrontmatter(
        title="Test Article",
        type="concept",
        department="cac",
        sources=["src1", "src2"],
        created="2026-01-01",
        updated=updated,
        confidence="medium",
    )
    article = WikiArticle(
        frontmatter=fm,
        body="Some body text.",
        file_path=str(path),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(article.to_markdown(), encoding="utf-8")


# ---------------------------------------------------------------------------
# TestRunMaintenance
# ---------------------------------------------------------------------------


class TestRunMaintenance:
    @pytest.mark.asyncio
    async def test_run_maintenance_calls_lint_department(self, tmp_path: Path) -> None:
        """run_maintenance calls linter.lint_department with the given dept_id."""
        agent, mock_linter, _, _, _ = _make_agent(tmp_path)
        (tmp_path / "cac").mkdir(parents=True, exist_ok=True)

        with patch.object(agent, "_register_heartbeat", new_callable=AsyncMock):
            await agent.run_maintenance("cac")

        mock_linter.lint_department.assert_called_once_with("cac")

    @pytest.mark.asyncio
    async def test_run_maintenance_calls_write_lint_report(self, tmp_path: Path) -> None:
        """run_maintenance calls linter.write_lint_report with the lint report."""
        agent, mock_linter, _, _, _ = _make_agent(tmp_path)
        (tmp_path / "cac").mkdir(parents=True, exist_ok=True)

        expected_report = LintReport(
            dept_id="cac",
            timestamp="2026-04-07T00:00:00+00:00",
            results=[],
            articles_scanned=2,
        )
        mock_linter.lint_department.return_value = expected_report

        with patch.object(agent, "_register_heartbeat", new_callable=AsyncMock):
            await agent.run_maintenance("cac")

        mock_linter.write_lint_report.assert_called_once_with("cac", expected_report)

    @pytest.mark.asyncio
    async def test_run_maintenance_calls_log_writer_append_entry(self, tmp_path: Path) -> None:
        """run_maintenance calls log_writer.append_entry to record the operation."""
        agent, _, mock_log_writer, _, _ = _make_agent(tmp_path)
        (tmp_path / "cac").mkdir(parents=True, exist_ok=True)

        with patch.object(agent, "_register_heartbeat", new_callable=AsyncMock):
            await agent.run_maintenance("cac")

        mock_log_writer.append_entry.assert_called_once()
        call_kwargs = mock_log_writer.append_entry.call_args
        # First positional arg must be the dept_id
        assert call_kwargs[0][0] == "cac"

    @pytest.mark.asyncio
    async def test_run_maintenance_returns_summary_dict(self, tmp_path: Path) -> None:
        """run_maintenance returns a dict with dept_id and articles_scanned."""
        agent, _, _, _, _ = _make_agent(tmp_path)
        (tmp_path / "cac").mkdir(parents=True, exist_ok=True)

        with patch.object(agent, "_register_heartbeat", new_callable=AsyncMock):
            result = await agent.run_maintenance("cac")

        assert isinstance(result, dict)
        assert result["dept_id"] == "cac"
        assert "articles_scanned" in result


# ---------------------------------------------------------------------------
# TestPruneOldArticles
# ---------------------------------------------------------------------------


class TestPruneOldArticles:
    def test_prune_old_articles_moves_stale_to_archive(self, tmp_path: Path) -> None:
        """_prune_old_articles moves articles older than max_age_days to archive/."""
        dept_dir = tmp_path / "cac"
        old_article = dept_dir / "concepts" / "old-concept.md"
        _write_article(old_article, updated="2024-01-01")  # ~15 months ago

        agent, _, _, _, _ = _make_agent(tmp_path)
        archived = agent._prune_old_articles("cac", max_age_days=30)

        assert len(archived) == 1
        archive_dir = tmp_path / "cac" / "archive"
        assert archive_dir.exists()
        assert (archive_dir / "old-concept.md").exists()
        assert not old_article.exists()

    def test_prune_old_articles_keeps_recent_articles(self, tmp_path: Path) -> None:
        """_prune_old_articles does not touch articles within max_age_days."""
        dept_dir = tmp_path / "cac"
        recent_article = dept_dir / "concepts" / "recent-concept.md"
        _write_article(recent_article, updated="2026-04-07")  # today

        agent, _, _, _, _ = _make_agent(tmp_path)
        archived = agent._prune_old_articles("cac", max_age_days=365)

        assert archived == []
        assert recent_article.exists()

    def test_prune_old_articles_creates_archive_dir(self, tmp_path: Path) -> None:
        """_prune_old_articles creates the archive/ directory if it does not exist."""
        dept_dir = tmp_path / "cac"
        old_article = dept_dir / "concepts" / "old.md"
        _write_article(old_article, updated="2020-01-01")

        agent, _, _, _, _ = _make_agent(tmp_path)
        agent._prune_old_articles("cac", max_age_days=30)

        assert (tmp_path / "cac" / "archive").is_dir()

    def test_prune_old_articles_skips_reserved_files(self, tmp_path: Path) -> None:
        """_prune_old_articles never moves index.md, log.md, lint-report.md."""
        dept_dir = tmp_path / "cac"
        dept_dir.mkdir(parents=True, exist_ok=True)
        (dept_dir / "index.md").write_text("# index\n", encoding="utf-8")
        (dept_dir / "log.md").write_text("# log\n", encoding="utf-8")
        (dept_dir / "lint-report.md").write_text("# lint\n", encoding="utf-8")

        agent, _, _, _, _ = _make_agent(tmp_path)
        archived = agent._prune_old_articles("cac", max_age_days=0)

        assert archived == []


# ---------------------------------------------------------------------------
# TestRunAllDepartments
# ---------------------------------------------------------------------------


class TestRunAllDepartments:
    @pytest.mark.asyncio
    async def test_run_all_departments_calls_run_maintenance_for_each_dept(
        self, tmp_path: Path
    ) -> None:
        """run_all_departments calls run_maintenance once per department."""
        agent, _, _, _, mock_dept_router = _make_agent(tmp_path)
        mock_dept_router.list_departments.return_value = ["cac", "hr", "treasury"]

        for dept in ["cac", "hr", "treasury"]:
            (tmp_path / dept).mkdir(parents=True, exist_ok=True)

        with patch.object(agent, "_register_heartbeat", new_callable=AsyncMock):
            results = await agent.run_all_departments()

        assert "cac" in results
        assert "hr" in results
        assert "treasury" in results
        assert len(results) == 3
