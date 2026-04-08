"""Department router — maps compile events to vault subdirectories.

Enforces data boundaries: a CAC event may only write to
``{vault_path}/cac/``, never to ``hr/`` or any other department directory.
The special dept_id ``"shared"`` writes to ``{vault_path}/shared/`` and
maps to the ``shared_policies`` Qdrant collection.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from services.wiki_compiler.src.config import WikiSettings

logger = logging.getLogger("wiki-compiler.dept_router")

_SHARED_DEPT_ID = "shared"
_SHARED_COLLECTION = "shared_policies"


class DeptRouter:
    """Maps department IDs and article types to concrete vault file paths."""

    def __init__(self, settings: WikiSettings) -> None:
        self._vault_path = Path(settings.vault_path)

        with open(settings.departments_config, encoding="utf-8") as fh:
            raw = json.load(fh)
        self._departments: dict[str, dict] = raw.get("departments", {})

        with open(settings.wiki_schema_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self._article_types: dict[str, dict] = raw.get("article_types", {})

        logger.info(
            "DeptRouter loaded departments=%s schema_types=%s vault=%s",
            list(self._departments),
            list(self._article_types),
            self._vault_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_vault_path(
        self,
        dept_id: str,
        article_type: str,
        slug: str,
        date: str | None = None,
    ) -> Path:
        """Return the full file path for an article.

        Args:
            dept_id: Department identifier, e.g. ``"cac"`` or ``"shared"``.
            article_type: One of the keys in wiki_schema article_types.
            slug: URL-safe article slug, e.g. ``"lcr"`` or ``"funding-update"``.
            date: ISO date string ``"YYYY-MM-DD"``, required for date-based
                  filename patterns such as ``{date}-{slug}.md``.

        Returns:
            Absolute :class:`Path` object for the target file.

        Raises:
            ValueError: If *dept_id* is unknown or *article_type* is unknown.
        """
        # Validate department (shared is always allowed)
        if dept_id != _SHARED_DEPT_ID and dept_id not in self._departments:
            raise ValueError(
                f"Unknown department: {dept_id!r}. "
                f"Valid options: {sorted(self._departments)} or 'shared'."
            )

        directory = self.get_article_directory(article_type)
        filename = self._build_filename(article_type, slug, date)

        path = self._vault_path / dept_id / directory / filename
        logger.debug(
            "Resolved path dept=%s type=%s slug=%s → %s", dept_id, article_type, slug, path
        )
        return path

    def validate_write_path(self, path: Path) -> bool:
        """Return True only if *path* is a child of the configured vault root.

        Uses :meth:`Path.resolve` to expand ``..`` components before the
        comparison, preventing path-traversal attacks.

        Args:
            path: Candidate write target.

        Returns:
            ``True`` when the resolved path is inside the vault; ``False``
            otherwise.
        """
        try:
            resolved = path.resolve()
            vault_resolved = self._vault_path.resolve()
            return resolved.is_relative_to(vault_resolved)
        except (OSError, ValueError):
            return False

    def get_dept_config(self, dept_id: str) -> dict:
        """Return the full department config dict for *dept_id*.

        Raises:
            ValueError: If *dept_id* is not in departments.json and is not
                        ``"shared"``.
        """
        if dept_id == _SHARED_DEPT_ID:
            return {"name": "Shared", "dataAccess": {"wikiCollection": _SHARED_COLLECTION}}
        if dept_id not in self._departments:
            raise ValueError(
                f"Unknown department: {dept_id!r}. "
                f"Valid options: {sorted(self._departments)}."
            )
        return self._departments[dept_id]

    def get_collection_for_dept(self, dept_id: str) -> str:
        """Return the Qdrant wiki collection name for *dept_id*.

        Raises:
            ValueError: If *dept_id* is unknown.
        """
        if dept_id == _SHARED_DEPT_ID:
            return _SHARED_COLLECTION
        config = self.get_dept_config(dept_id)
        return config["dataAccess"]["wikiCollection"]

    def get_article_directory(self, article_type: str) -> str:
        """Return the vault subdirectory name for *article_type*.

        Example: ``"concept"`` → ``"concepts"``

        Raises:
            ValueError: If *article_type* is not defined in wiki_schema.json.
        """
        if article_type not in self._article_types:
            raise ValueError(
                f"Unknown article_type: {article_type!r}. "
                f"Valid options: {sorted(self._article_types)}."
            )
        return self._article_types[article_type]["directory"]

    def list_departments(self) -> list[str]:
        """Return a sorted list of all department IDs from departments.json.

        Note: ``"shared"`` is a synthetic department and is not included here;
        it is accepted by :meth:`resolve_vault_path` but is not persisted in
        departments.json.
        """
        return sorted(self._departments.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_filename(self, article_type: str, slug: str, date: str | None) -> str:
        """Expand the filename_pattern from wiki_schema for *article_type*."""
        pattern: str = self._article_types[article_type]["filename_pattern"]
        return pattern.format(slug=slug, date=date or "")
