"""Scheduled wiki maintenance — lint, prune, gap detection."""
from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx
import structlog

from .config import WikiSettings
from .dept_router import DeptRouter
from .index_manager import IndexManager
from .linter import WikiLinter
from .log_writer import LogWriter

logger = structlog.get_logger("wiki-compiler.maintenance")

# Reserved filenames that must never be moved or modified by the maintenance agent.
_RESERVED_FILENAMES = {"index.md", "log.md", "lint-report.md"}


class MaintenanceAgent:
    """Orchestrates scheduled wiki health checks: lint, prune, index rebuild, heartbeat.

    This agent never generates staging proposals and never writes to
    ``/data/mirror/`` or ``/data/staging/``.  It operates entirely within the
    configured Obsidian vault.
    """

    def __init__(
        self,
        settings: WikiSettings,
        linter: WikiLinter,
        log_writer: LogWriter,
        index_manager: IndexManager,
        dept_router: DeptRouter,
    ) -> None:
        self._settings = settings
        self._vault = Path(settings.vault_path)
        self._linter = linter
        self._log_writer = log_writer
        self._index_manager = index_manager
        self._dept_router = dept_router

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_maintenance(self, dept_id: str) -> dict:
        """Orchestrate a full maintenance pass for *dept_id*.

        Steps:
        1. Lint the department vault.
        2. Write the lint report to ``lint-report.md``.
        3. Prune articles older than ``max_age_days`` to ``archive/``.
        4. Rebuild the department index.
        5. Append a summary log entry.
        6. Fire-and-forget heartbeat to Paperclip.

        Returns:
            A summary dict with keys: ``dept_id``, ``articles_scanned``,
            ``issues_found``, ``archived_count``.
        """
        logger.info("maintenance.start", dept_id=dept_id)

        # Step 1 — lint
        report = self._linter.lint_department(dept_id)

        # Step 2 — write lint report
        self._linter.write_lint_report(dept_id, report)

        # Step 3 — prune stale articles
        archived = self._prune_old_articles(dept_id)

        # Step 4 — rebuild index
        self._index_manager.rebuild_index(dept_id)

        # Step 5 — log entry
        description = (
            f"Lint complete: {report.issues_found} issues across "
            f"{report.articles_scanned} articles. "
            f"{len(archived)} article(s) archived."
        )
        self._log_writer.append_entry(
            dept_id,
            "maintenance",
            description,
            pages_affected=archived or None,
        )

        # Step 6 — heartbeat (fire-and-forget)
        await self._register_heartbeat()

        summary = {
            "dept_id": dept_id,
            "articles_scanned": report.articles_scanned,
            "issues_found": report.issues_found,
            "archived_count": len(archived),
        }
        logger.info("maintenance.complete", **summary)
        return summary

    async def run_all_departments(self) -> dict:
        """Run :meth:`run_maintenance` for every department in ``departments.json``.

        Returns:
            A dict mapping each ``dept_id`` to the summary dict returned by
            :meth:`run_maintenance`.
        """
        dept_ids = self._dept_router.list_departments()
        results: dict[str, dict] = {}
        for dept_id in dept_ids:
            results[dept_id] = await self.run_maintenance(dept_id)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _prune_old_articles(
        self, dept_id: str, max_age_days: int = 365
    ) -> list[str]:
        """Move articles older than *max_age_days* to ``{dept_dir}/archive/``.

        Only files whose ``updated`` frontmatter date is older than
        *max_age_days* are moved.  Reserved files (``index.md``, ``log.md``,
        ``lint-report.md``) and any files already inside ``archive/`` are
        skipped.  Frontmatter parse errors are logged and the file is left in
        place.

        Args:
            dept_id: Department identifier.
            max_age_days: Files with an ``updated`` date older than this many
                days are archived.  Defaults to 365.

        Returns:
            Vault-relative paths of every file that was moved.
        """
        dept_dir = self._vault / dept_id
        if not dept_dir.exists():
            logger.warning("maintenance.prune.dept_dir_missing", dept_id=dept_id)
            return []

        archive_dir = dept_dir / "archive"
        now = datetime.now(tz=UTC)
        archived_paths: list[str] = []

        for md_file in sorted(dept_dir.rglob("*.md")):
            # Never touch reserved files
            if md_file.name in _RESERVED_FILENAMES:
                continue
            # Never touch files already inside archive/
            try:
                md_file.relative_to(archive_dir)
                continue  # path is inside archive/
            except ValueError:
                pass  # not under archive/ — proceed

            # Parse updated date from frontmatter
            try:
                text = md_file.read_text(encoding="utf-8")
                from .models import WikiArticle  # local import to avoid circular
                article = WikiArticle.from_markdown(
                    text, file_path=str(md_file.relative_to(self._vault))
                )
                updated_dt = datetime.fromisoformat(
                    article.frontmatter.updated
                ).replace(tzinfo=UTC)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "maintenance.prune.parse_failed",
                    file=str(md_file),
                    error=str(exc),
                )
                continue

            age_days = (now - updated_dt).days
            if age_days <= max_age_days:
                continue

            # Move to archive/
            archive_dir.mkdir(parents=True, exist_ok=True)
            dest = archive_dir / md_file.name
            shutil.move(str(md_file), str(dest))
            rel_path = str(dest.relative_to(self._vault))
            archived_paths.append(rel_path)
            logger.info(
                "maintenance.prune.archived",
                src=str(md_file),
                dest=str(dest),
                age_days=age_days,
            )

        return archived_paths

    async def _register_heartbeat(self) -> None:
        """POST a heartbeat to Paperclip (fire-and-forget).

        Failures are logged at WARNING level and never propagate.
        """
        url = f"{self._settings.paperclip_url}/api/heartbeat"
        payload = {
            "agent_name": "wiki-maintenance-agent",
            "department": "shared",
            "agent_role": "worker",
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(url, json=payload)
            logger.info("maintenance.heartbeat_sent", url=url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("maintenance.heartbeat_failed", url=url, error=str(exc))
