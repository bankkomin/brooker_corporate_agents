"""IndexManager — maintains each department's index.md in the Obsidian vault."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from services.wiki_compiler.src.models import WikiArticle

logger = logging.getLogger("wiki-compiler.index_manager")

# Maps vault subdirectory names to index.md section headings.
_SUBDIR_TO_CATEGORY: dict[str, str] = {
    "concepts": "## Concepts",
    "decisions": "## Decisions",
    "meeting-notes": "## Meeting Notes",
    "entities": "## Entities",
    "trends": "## Trends",
}

# Canonical order for sections in the index.
_CATEGORY_ORDER: list[str] = [
    "## Concepts",
    "## Decisions",
    "## Meeting Notes",
    "## Entities",
    "## Trends",
]

_EXCLUDED_FILES = {"index.md", "log.md", "lint-report.md"}


class IndexManager:
    """Auto-maintains `{vault}/{dept_id}/index.md` when articles are added or changed."""

    def __init__(self, vault_path: Path) -> None:
        self._vault = vault_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_index(self, dept_id: str, article: WikiArticle) -> None:
        """Upsert one entry in the department index for *article*.

        Finds (or creates) the correct category section based on the article's
        subdirectory, replaces any existing entry for the same filename, and
        sorts entries within the section by date descending.
        """
        index_path = self._vault / dept_id / "index.md"
        category = self._category_for_article(article)
        entry_line = self._build_entry_line(article)
        filename_stem = Path(article.file_path).stem

        if index_path.exists():
            text = index_path.read_text(encoding="utf-8")
        else:
            text = self._skeleton_index(dept_id)

        text = self._upsert_entry(text, category, entry_line, filename_stem)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(text, encoding="utf-8")
        logger.info("index_manager: updated index for %s/%s", dept_id, article.file_path)

    def rebuild_index(self, dept_id: str) -> None:
        """Regenerate the entire index.md by scanning all articles on disk.

        Groups files by subdirectory → category heading, then writes a fresh
        index.md with entries sorted by date descending within each section.
        """
        dept_dir = self._vault / dept_id
        sections: dict[str, list[str]] = {cat: [] for cat in _CATEGORY_ORDER}

        if dept_dir.exists():
            for md_file in sorted(dept_dir.rglob("*.md")):
                if md_file.name in _EXCLUDED_FILES:
                    continue
                # Determine category from the immediate parent subdirectory name
                subdir = md_file.parent.name
                category = _SUBDIR_TO_CATEGORY.get(subdir)
                if category is None:
                    continue
                try:
                    article = WikiArticle.from_markdown(
                        md_file.read_text(encoding="utf-8"),
                        file_path=str(md_file.relative_to(self._vault)),
                    )
                    entry_line = self._build_entry_line(article)
                    sections[category].append(entry_line)
                except Exception:
                    logger.warning("index_manager: could not parse %s, skipping", md_file)

        text = self._skeleton_index(dept_id)
        for category, entries in sections.items():
            if entries:
                # Sort by the date token embedded in the entry (last bracketed date)
                entries.sort(key=self._entry_sort_key, reverse=True)
                text = self._upsert_section_entries(text, category, entries)

        index_path = dept_dir / "index.md"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(text, encoding="utf-8")
        logger.info("index_manager: rebuilt index for %s", dept_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _category_for_article(article: WikiArticle) -> str:
        """Return the ## heading for this article based on its subdirectory."""
        # file_path is like "cac/concepts/slug.md"
        parts = Path(article.file_path).parts
        # parts[-2] is the subdirectory (concepts, decisions, …)
        subdir = parts[-2] if len(parts) >= 2 else ""
        return _SUBDIR_TO_CATEGORY.get(subdir, "## Concepts")

    @staticmethod
    def _build_entry_line(article: WikiArticle) -> str:
        """Format one index entry line for *article*."""
        stem = Path(article.file_path).stem
        title = article.frontmatter.title
        source_count = len(article.frontmatter.sources)
        date = article.frontmatter.updated
        return f"- [[{stem}]] — {title} ({source_count} sources) [{date}]"

    @staticmethod
    def _entry_sort_key(line: str) -> str:
        """Extract the date string from an entry line for sorting purposes."""
        match = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", line)
        return match.group(1) if match else ""

    def _skeleton_index(self, dept_id: str) -> str:
        """Return a fresh index.md skeleton string."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        dept_upper = dept_id.upper()
        lines: list[str] = [
            "---",
            f"title: {dept_upper} Knowledge Base",
            "type: index",
            f"department: {dept_id}",
            f"updated: {today}",
            "---",
            "",
            f"# {dept_upper} Knowledge Base",
            "",
        ]
        for category in _CATEGORY_ORDER:
            lines.append(category)
            lines.append("")  # blank line after heading
        return "\n".join(lines)

    def _upsert_entry(
        self, text: str, category: str, entry_line: str, filename_stem: str
    ) -> str:
        """Insert or replace an entry under *category* in *text*."""
        # Ensure the category heading exists
        if category not in text:
            text = self._add_category(text, category)

        lines = text.splitlines(keepends=True)
        in_section = False
        section_entries: list[tuple[int, str]] = []  # (line_index, content)
        existing_idx: int | None = None

        for i, line in enumerate(lines):
            stripped = line.rstrip("\n")
            if stripped == category:
                in_section = True
                continue
            if in_section:
                # Any ## heading ends the current section
                if stripped.startswith("## ") and stripped != category:
                    break
                if stripped.startswith("- [["):
                    section_entries.append((i, stripped))
                    if filename_stem in stripped:
                        existing_idx = i

        if existing_idx is not None:
            # Replace the existing line
            lines[existing_idx] = entry_line + "\n"
        else:
            # Find the insertion point: after the category heading line
            insert_after = None
            for i, line in enumerate(lines):
                if line.rstrip("\n") == category:
                    insert_after = i
                    break
            if insert_after is not None:
                lines.insert(insert_after + 1, entry_line + "\n")

        # Re-sort entries within this section
        text = "".join(lines)
        text = self._sort_section(text, category)
        return text

    def _upsert_section_entries(
        self, text: str, category: str, entries: list[str]
    ) -> str:
        """Replace the entire entry list under *category* with *entries*."""
        if category not in text:
            text = self._add_category(text, category)

        lines = text.splitlines(keepends=True)
        section_start: int | None = None
        entry_start: int | None = None
        entry_end: int | None = None

        for i, line in enumerate(lines):
            stripped = line.rstrip("\n")
            if stripped == category:
                section_start = i
                continue
            if section_start is not None and entry_start is None and stripped.startswith("- [["):
                entry_start = i
            ends_entries = (
                entry_start is not None
                and not stripped.startswith("- [[")
                and stripped != ""
                and (stripped.startswith("## ") or not stripped.startswith("- "))
            )
            if ends_entries:
                entry_end = i
                break

        if entry_start is None:
            # No entries yet — insert after section heading
            if section_start is not None:
                for entry in entries:
                    lines.insert(section_start + 1, entry + "\n")
                return "".join(lines)
        else:
            if entry_end is None:
                entry_end = len(lines)
            # Remove old entries, insert new ones
            new_entry_lines = [e + "\n" for e in entries]
            lines[entry_start:entry_end] = new_entry_lines

        return "".join(lines)

    @staticmethod
    def _add_category(text: str, category: str) -> str:
        """Append *category* heading at the end of *text* if missing."""
        return text.rstrip("\n") + f"\n\n{category}\n"

    def _sort_section(self, text: str, category: str) -> str:
        """Sort entry lines within *category* by date descending, in-place."""
        lines = text.splitlines(keepends=True)
        section_start: int | None = None
        entry_indices: list[int] = []

        for i, line in enumerate(lines):
            stripped = line.rstrip("\n")
            if stripped == category:
                section_start = i
                continue
            if section_start is not None:
                if stripped.startswith("## ") and stripped != category:
                    break
                if stripped.startswith("- [["):
                    entry_indices.append(i)

        if len(entry_indices) > 1:
            entry_lines = [lines[i].rstrip("\n") for i in entry_indices]
            entry_lines.sort(key=self._entry_sort_key, reverse=True)
            for idx, line_idx in enumerate(entry_indices):
                lines[line_idx] = entry_lines[idx] + "\n"

        return "".join(lines)
