"""Unit tests for DeptRouter — department routing and boundary enforcement."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from services.wiki_compiler.src.config import WikiSettings
from services.wiki_compiler.src.dept_router import DeptRouter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DEPARTMENTS = {
    "version": "1.0",
    "departments": {
        "cac": {
            "name": "Capital Allocation Committee",
            "shortName": "CAC",
            "description": "Treasury, capital adequacy, ALM, and funding operations",
            "agents": ["liquidity", "capital", "alm", "funding"],
            "dataAccess": {
                "qdrantCollections": ["cac_docs", "cac_chat", "cac_knowledge", "shared_policies"],
                "mirrorPaths": ["/data/mirror/alco/"],
                "excelFiles": ["ALCO_Tracker.xlsx"],
                "sensitivityLevel": "confidential",
                "vaultPath": "/mnt/obsidian-vault/cac",
                "wikiCollection": "cac_knowledge",
            },
        }
    },
    "globalAccess": {
        "sharedCollections": ["shared_policies"],
        "roles": {
            "ceo": {"canRead": ["*"], "canApprove": ["*"]},
            "cfo": {"canRead": ["cac", "risk"], "canApprove": ["cac"]},
        },
    },
}

WIKI_SCHEMA = {
    "version": "1.0",
    "article_types": {
        "concept": {
            "directory": "concepts",
            "filename_pattern": "{slug}.md",
        },
        "decision": {
            "directory": "decisions",
            "filename_pattern": "{date}-{slug}.md",
        },
        "meeting-note": {
            "directory": "meeting-notes",
            "filename_pattern": "{date}-{slug}.md",
        },
        "entity": {
            "directory": "entities",
            "filename_pattern": "{slug}.md",
        },
        "escalation": {
            "directory": "decisions",
            "filename_pattern": "{date}-escalation-{slug}.md",
        },
        "source-summary": {
            "directory": "concepts",
            "filename_pattern": "source-{slug}.md",
        },
    },
}


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Write temporary departments.json and wiki_schema.json; return config dir."""
    (tmp_path / "departments.json").write_text(json.dumps(DEPARTMENTS))
    (tmp_path / "wiki_schema.json").write_text(json.dumps(WIKI_SCHEMA))
    return tmp_path


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """Create a temporary vault root directory."""
    vault_dir = tmp_path / "obsidian-vault"
    vault_dir.mkdir()
    return vault_dir


@pytest.fixture()
def router(config_dir: Path, vault: Path) -> DeptRouter:
    """Return a DeptRouter wired to temporary config and vault."""
    settings = WikiSettings(
        vault_path=str(vault),
        departments_config=str(config_dir / "departments.json"),
        wiki_schema_path=str(config_dir / "wiki_schema.json"),
    )
    return DeptRouter(settings)


# ---------------------------------------------------------------------------
# resolve_vault_path
# ---------------------------------------------------------------------------

def test_resolve_vault_path_concept(router: DeptRouter, vault: Path) -> None:
    """concept articles use {slug}.md, no date required."""
    result = router.resolve_vault_path("cac", "concept", "lcr")
    expected = vault / "cac" / "concepts" / "lcr.md"
    assert result == expected


def test_resolve_vault_path_decision_with_date(router: DeptRouter, vault: Path) -> None:
    """decision articles use {date}-{slug}.md."""
    result = router.resolve_vault_path("cac", "decision", "funding-update", "2026-04-07")
    expected = vault / "cac" / "decisions" / "2026-04-07-funding-update.md"
    assert result == expected


def test_resolve_vault_path_shared_escalation(router: DeptRouter, vault: Path) -> None:
    """shared dept writes under shared/, not cac/ or any other dept."""
    result = router.resolve_vault_path("shared", "escalation", "lcr-breach", "2026-04-07")
    expected = vault / "shared" / "decisions" / "2026-04-07-escalation-lcr-breach.md"
    assert result == expected
    # Confirm it is NOT under cac/
    assert "cac" not in result.parts


def test_resolve_vault_path_unknown_dept_raises(router: DeptRouter) -> None:
    """Unknown dept_id must raise ValueError — not silently create a rogue directory."""
    with pytest.raises(ValueError, match="Unknown department"):
        router.resolve_vault_path("hr", "concept", "headcount")


# ---------------------------------------------------------------------------
# validate_write_path
# ---------------------------------------------------------------------------

def test_validate_write_path_accepts_valid_path(router: DeptRouter, vault: Path) -> None:
    """A path inside the vault passes validation."""
    valid = vault / "cac" / "concepts" / "lcr.md"
    assert router.validate_write_path(valid) is True


def test_validate_write_path_rejects_traversal(router: DeptRouter, vault: Path) -> None:
    """Path traversal outside the vault must be rejected."""
    traversal = vault / ".." / ".." / "etc" / "passwd"
    assert router.validate_write_path(traversal) is False


# ---------------------------------------------------------------------------
# get_collection_for_dept
# ---------------------------------------------------------------------------

def test_get_collection_for_dept_cac(router: DeptRouter) -> None:
    """CAC department maps to cac_knowledge collection."""
    assert router.get_collection_for_dept("cac") == "cac_knowledge"


# ---------------------------------------------------------------------------
# list_departments
# ---------------------------------------------------------------------------

def test_list_departments_includes_cac(router: DeptRouter) -> None:
    """list_departments must return at least ['cac']; shared is synthetic."""
    depts = router.list_departments()
    assert "cac" in depts
