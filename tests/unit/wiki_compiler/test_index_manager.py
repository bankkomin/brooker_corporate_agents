"""Tests for wiki-compiler IndexManager."""
from __future__ import annotations

from pathlib import Path

from services.wiki_compiler.src.index_manager import IndexManager
from services.wiki_compiler.src.models import ArticleFrontmatter, WikiArticle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_article(
    title: str = "Liquidity Coverage Ratio",
    article_type: str = "concept",
    dept: str = "cac",
    slug: str = "liquidity-coverage-ratio",
    date: str = "2026-04-07",
    sources: int = 3,
) -> WikiArticle:
    """Build a minimal WikiArticle for testing."""
    subdir = {
        "concept": "concepts",
        "decision": "decisions",
        "meeting-note": "meeting-notes",
        "entity": "entities",
        "trend": "trends",
    }[article_type]
    date_prefix = article_type not in ("concept", "entity", "trend")
    filename = f"{date}-{slug}.md" if date_prefix else f"{slug}.md"
    fm = ArticleFrontmatter(
        title=title,
        type=article_type,  # type: ignore[arg-type]
        department=dept,
        sources=[f"src-{i}" for i in range(sources)],
        created=date,
        updated=date,
        confidence="high",
    )
    return WikiArticle(
        frontmatter=fm,
        body="## Summary\n\nTest body.",
        file_path=f"{dept}/{subdir}/{filename}",
    )


def init_vault(vault: Path, dept_id: str = "cac") -> Path:
    """Create department directory structure under vault."""
    dept_dir = vault / dept_id
    for subdir in ("concepts", "decisions", "meeting-notes", "entities", "trends"):
        (dept_dir / subdir).mkdir(parents=True, exist_ok=True)
    return dept_dir


# ---------------------------------------------------------------------------
# TestUpdateIndex
# ---------------------------------------------------------------------------

class TestUpdateIndex:
    def test_update_index_adds_entry_to_correct_section(self, tmp_path: Path) -> None:
        """update_index writes an entry under the matching ## Concepts section."""
        dept_dir = init_vault(tmp_path)
        mgr = IndexManager(tmp_path)
        article = make_article()  # concept → ## Concepts

        mgr.update_index("cac", article)

        index_text = (dept_dir / "index.md").read_text()
        assert "## Concepts" in index_text
        assert "liquidity-coverage-ratio" in index_text
        assert "Liquidity Coverage Ratio" in index_text

    def test_update_index_replaces_existing_entry_same_filename(self, tmp_path: Path) -> None:
        """Calling update_index twice for the same filename replaces the line."""
        init_vault(tmp_path)
        mgr = IndexManager(tmp_path)
        article_v1 = make_article(sources=1)
        article_v2 = make_article(sources=5)

        mgr.update_index("cac", article_v1)
        mgr.update_index("cac", article_v2)

        index_text = (tmp_path / "cac" / "index.md").read_text()
        # Only one entry for this slug
        assert index_text.count("liquidity-coverage-ratio") == 1
        # Updated source count present
        assert "5 sources" in index_text

    def test_update_index_creates_section_if_missing(self, tmp_path: Path) -> None:
        """update_index creates the category heading when it is absent from index.md."""
        dept_dir = init_vault(tmp_path)
        # Write an index.md that lacks ## Decisions
        skeleton = (
            "---\ntitle: CAC Knowledge Base\ntype: index\n---\n\n"
            "# CAC Knowledge Base\n\n## Concepts\n"
        )
        (dept_dir / "index.md").write_text(skeleton)
        mgr = IndexManager(tmp_path)
        article = make_article(
            title="Funding Update",
            article_type="decision",
            slug="funding-update",
        )

        mgr.update_index("cac", article)

        index_text = (dept_dir / "index.md").read_text()
        assert "## Decisions" in index_text
        assert "funding-update" in index_text

    def test_rebuild_index_generates_complete_index(self, tmp_path: Path) -> None:
        """rebuild_index scans vault files and produces a full index.md."""
        dept_dir = init_vault(tmp_path)
        # Write a concept article file on disk
        concept_file = dept_dir / "concepts" / "liquidity-coverage-ratio.md"
        article = make_article()
        concept_file.write_text(article.to_markdown())

        mgr = IndexManager(tmp_path)
        mgr.rebuild_index("cac")

        index_text = (dept_dir / "index.md").read_text()
        assert "## Concepts" in index_text
        assert "liquidity-coverage-ratio" in index_text
        # All required section headings present
        for heading in ("## Decisions", "## Meeting Notes", "## Entities", "## Trends"):
            assert heading in index_text

    def test_rebuild_index_on_empty_vault_creates_skeleton(self, tmp_path: Path) -> None:
        """rebuild_index with no articles creates an index skeleton with empty sections."""
        init_vault(tmp_path)
        mgr = IndexManager(tmp_path)
        mgr.rebuild_index("cac")

        index_text = (tmp_path / "cac" / "index.md").read_text()
        all_headings = (
            "## Concepts", "## Decisions", "## Meeting Notes", "## Entities", "## Trends"
        )
        for heading in all_headings:
            assert heading in index_text
        # No article entries
        assert "[[" not in index_text
