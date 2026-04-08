"""Linker — scans articles for [[backlinks]] and updates related: frontmatter."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from services.wiki_compiler.src.models import WikiArticle

logger = logging.getLogger("wiki-compiler.linker")

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


class Linker:
    """Maintains bidirectional ``related:`` links between wiki articles."""

    def __init__(self, vault_path: Path) -> None:
        self._vault = vault_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_backlinks(self, dept_id: str, article: WikiArticle) -> list[str]:
        """Scan *article* body for ``[[page-name]]`` refs and update related: fields.

        For each referenced page that exists on disk inside the department
        vault, the current article's stem is appended to that page's
        ``related:`` list (idempotent — no duplicates added).

        Args:
            dept_id: Department to search within.
            article: The source article containing the wikilinks.

        Returns:
            List of file paths (strings) for pages that were updated.
        """
        dept_dir = self._vault / dept_id
        source_stem = Path(article.file_path).stem
        references = _WIKILINK_RE.findall(article.body)

        updated: list[str] = []
        for ref in references:
            target_path = self._find_page(dept_dir, ref)
            if target_path is None:
                logger.debug("linker: [[%s]] not found in %s — skipping", ref, dept_id)
                continue

            target_article = WikiArticle.from_markdown(
                target_path.read_text(encoding="utf-8"),
                file_path=str(target_path.relative_to(self._vault)),
            )

            if source_stem not in target_article.frontmatter.related:
                target_article.frontmatter.related.append(source_stem)
                target_path.write_text(target_article.to_markdown(), encoding="utf-8")
                updated.append(str(target_path))
                logger.info(
                    "linker: added backlink %s → %s", source_stem, target_path.name
                )

        return updated

    def find_broken_links(self, dept_id: str) -> list[str]:
        """Return page names referenced by ``[[wikilinks]]`` with no matching file.

        Scans all ``.md`` files in the department vault and collects every
        wikilink target that cannot be resolved to an existing file.

        Args:
            dept_id: Department to scan.

        Returns:
            Sorted list of unresolved page name strings (deduplicated).
        """
        dept_dir = self._vault / dept_id
        broken: set[str] = set()

        for md_file in dept_dir.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            for ref in _WIKILINK_RE.findall(text):
                if self._find_page(dept_dir, ref) is None:
                    broken.add(ref)

        return sorted(broken)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_page(dept_dir: Path, page_name: str) -> Path | None:
        """Search all subdirectories of *dept_dir* for ``{page_name}.md``.

        Args:
            dept_dir: Root directory of the department vault.
            page_name: The page stem (without ``.md`` extension).

        Returns:
            :class:`Path` to the first matching file, or ``None`` if not found.
        """
        target_name = f"{page_name}.md"
        matches = list(dept_dir.rglob(target_name))
        if matches:
            return matches[0]
        return None
