"""Tests for wiki-compiler LogWriter."""
from __future__ import annotations

from pathlib import Path

from services.wiki_compiler.src.log_writer import LogWriter

# ---------------------------------------------------------------------------
# TestLogWriter
# ---------------------------------------------------------------------------

class TestLogWriter:
    def test_append_entry_adds_parseable_entry(self, tmp_path: Path) -> None:
        """append_entry writes a dated ## heading with operation and description."""
        dept_dir = tmp_path / "cac"
        dept_dir.mkdir()
        writer = LogWriter(tmp_path)

        writer.append_entry("cac", "ingest", "Approved: Funding utilization update E8 → 78%")

        log_text = (dept_dir / "log.md").read_text(encoding="utf-8")
        assert "## [" in log_text
        assert "ingest" in log_text
        assert "Funding utilization update" in log_text

    def test_append_entry_with_pages_includes_pages_line(self, tmp_path: Path) -> None:
        """When pages_affected is supplied, the Pages: line is written."""
        dept_dir = tmp_path / "cac"
        dept_dir.mkdir()
        writer = LogWriter(tmp_path)
        pages = [
            "cac/decisions/2026-04-07-funding-update.md",
            "cac/concepts/funding-facilities.md",
        ]

        writer.append_entry("cac", "ingest", "Funding update", pages_affected=pages)

        log_text = (dept_dir / "log.md").read_text()
        assert "Pages:" in log_text
        assert "cac/decisions/2026-04-07-funding-update.md" in log_text
        assert "cac/concepts/funding-facilities.md" in log_text

    def test_append_entry_without_pages_omits_pages_line(self, tmp_path: Path) -> None:
        """When pages_affected is None, no Pages: line appears."""
        dept_dir = tmp_path / "cac"
        dept_dir.mkdir()
        writer = LogWriter(tmp_path)

        writer.append_entry("cac", "lint", "Lint scan complete", pages_affected=None)

        log_text = (dept_dir / "log.md").read_text()
        assert "Pages:" not in log_text

    def test_multiple_entries_append_in_order(self, tmp_path: Path) -> None:
        """Each subsequent call appends below the previous entry."""
        dept_dir = tmp_path / "cac"
        dept_dir.mkdir()
        writer = LogWriter(tmp_path)

        writer.append_entry("cac", "ingest", "First entry")
        writer.append_entry("cac", "rebuild", "Second entry")
        writer.append_entry("cac", "lint", "Third entry")

        log_text = (dept_dir / "log.md").read_text()
        pos_first = log_text.index("First entry")
        pos_second = log_text.index("Second entry")
        pos_third = log_text.index("Third entry")
        assert pos_first < pos_second < pos_third
