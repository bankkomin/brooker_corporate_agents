"""Tests for wiki-compiler Linker."""
from __future__ import annotations

from pathlib import Path

from services.wiki_compiler.src.linker import Linker
from services.wiki_compiler.src.models import ArticleFrontmatter, WikiArticle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_article(
    path: Path,
    title: str = "Test Article",
    article_type: str = "concept",
    dept: str = "cac",
    body: str = "Some body.",
    related: list[str] | None = None,
) -> WikiArticle:
    """Write a WikiArticle to disk and return it."""
    fm = ArticleFrontmatter(
        title=title,
        type=article_type,  # type: ignore[arg-type]
        department=dept,
        related=related or [],
        created="2026-04-07",
        updated="2026-04-07",
        confidence="high",
    )
    article = WikiArticle(
        frontmatter=fm,
        body=body,
        file_path=str(path),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(article.to_markdown())
    return article


# ---------------------------------------------------------------------------
# TestUpdateBacklinks
# ---------------------------------------------------------------------------

class TestUpdateBacklinks:
    def test_update_backlinks_finds_reference_and_updates_related(self, tmp_path: Path) -> None:
        """[[page-name]] in article body causes related field on target page to be updated."""
        dept_dir = tmp_path / "cac"
        # Create the referenced target article
        target_path = dept_dir / "concepts" / "funding-facilities.md"
        write_article(target_path, title="Funding Facilities")

        # Create the source article that links to the target
        source = write_article(
            dept_dir / "decisions" / "2026-04-07-funding-update.md",
            title="Funding Update",
            article_type="decision",
            body="See also [[funding-facilities]] for background.",
        )

        linker = Linker(tmp_path)
        updated = linker.update_backlinks("cac", source)

        assert len(updated) == 1
        # target file was updated
        target_text = target_path.read_text()
        assert "2026-04-07-funding-update" in target_text

    def test_update_backlinks_does_not_duplicate_existing_related(self, tmp_path: Path) -> None:
        """Running update_backlinks twice does not add the same related entry twice."""
        dept_dir = tmp_path / "cac"
        target_path = dept_dir / "concepts" / "funding-facilities.md"
        write_article(target_path, title="Funding Facilities")

        source = write_article(
            dept_dir / "decisions" / "2026-04-07-funding-update.md",
            title="Funding Update",
            article_type="decision",
            body="See [[funding-facilities]].",
        )

        linker = Linker(tmp_path)
        linker.update_backlinks("cac", source)
        linker.update_backlinks("cac", source)

        # Re-read target and count occurrences
        updated_article = WikiArticle.from_markdown(
            target_path.read_text(),
            file_path=str(target_path),
        )
        count = updated_article.frontmatter.related.count("2026-04-07-funding-update")
        assert count == 1

    def test_update_backlinks_skips_nonexistent_pages(self, tmp_path: Path) -> None:
        """References to pages that don't exist are silently skipped."""
        dept_dir = tmp_path / "cac"
        (dept_dir / "decisions").mkdir(parents=True)

        source = write_article(
            dept_dir / "decisions" / "2026-04-07-funding-update.md",
            title="Funding Update",
            article_type="decision",
            body="See [[does-not-exist]] and [[also-missing]].",
        )

        linker = Linker(tmp_path)
        updated = linker.update_backlinks("cac", source)

        assert updated == []

    # ------------------------------------------------------------------
    # TestFindBrokenLinks
    # ------------------------------------------------------------------

    def test_find_broken_links_detects_missing_references(self, tmp_path: Path) -> None:
        """find_broken_links returns page names that have no matching .md file."""
        dept_dir = tmp_path / "cac"
        write_article(
            dept_dir / "concepts" / "lcr.md",
            title="LCR",
            body="See [[nonexistent-page]] for details.",
        )

        linker = Linker(tmp_path)
        broken = linker.find_broken_links("cac")

        assert "nonexistent-page" in broken

    def test_find_broken_links_returns_empty_when_all_resolve(self, tmp_path: Path) -> None:
        """find_broken_links returns [] when every [[link]] has a matching file."""
        dept_dir = tmp_path / "cac"
        write_article(
            dept_dir / "concepts" / "funding-facilities.md",
            title="Funding Facilities",
        )
        write_article(
            dept_dir / "concepts" / "lcr.md",
            title="LCR",
            body="See [[funding-facilities]] for details.",
        )

        linker = Linker(tmp_path)
        broken = linker.find_broken_links("cac")

        assert broken == []
