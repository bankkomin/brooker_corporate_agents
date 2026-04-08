"""LogWriter — appends parseable entries to each department's log.md."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("wiki-compiler.log_writer")


class LogWriter:
    """Appends structured log entries to ``{vault}/{dept_id}/log.md``."""

    def __init__(self, vault_path: Path) -> None:
        self._vault = vault_path

    def append_entry(
        self,
        dept_id: str,
        operation: str,
        description: str,
        pages_affected: list[str] | None = None,
    ) -> None:
        """Append one log entry to the department log file.

        Format::

            ## [2026-04-07] ingest | Approved: Funding utilization update E8 → 78%
            Pages: cac/decisions/2026-04-07-funding-update.md, cac/concepts/funding-facilities.md

        The ``Pages:`` line is omitted when *pages_affected* is ``None`` or empty.

        Args:
            dept_id: Department identifier, e.g. ``"cac"``.
            operation: Short operation label, e.g. ``"ingest"``, ``"rebuild"``.
            description: Human-readable description of the log event.
            pages_affected: Optional list of vault-relative file paths that were
                touched by this operation.
        """
        log_path = self._vault / dept_id / "log.md"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        entry_lines: list[str] = [
            f"\n## [{date_str}] {operation} | {description}",
        ]
        if pages_affected:
            pages_str = ", ".join(pages_affected)
            entry_lines.append(f"Pages: {pages_str}")

        entry_text = "\n".join(entry_lines) + "\n"

        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(entry_text)

        logger.info("log_writer: appended entry to %s/%s/log.md", self._vault, dept_id)
