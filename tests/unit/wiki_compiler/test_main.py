"""Unit tests for wiki-compiler FastAPI endpoints."""
from __future__ import annotations

import contextlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MINIMAL_SCHEMA = {
    "version": "1.0",
    "article_types": {
        "decision": {
            "directory": "decisions",
            "filename_pattern": "{date}-{slug}.md",
            "sections": ["Summary", "Change Details", "Rationale"],
        },
        "concept": {
            "directory": "concepts",
            "filename_pattern": "{slug}.md",
            "sections": ["Summary", "Key Metrics"],
        },
        "meeting-note": {
            "directory": "meeting-notes",
            "filename_pattern": "{date}-{slug}.md",
            "sections": ["Agenda", "Discussion", "Action Items"],
        },
        "source-summary": {
            "directory": "source-summaries",
            "filename_pattern": "{date}-{slug}.md",
            "sections": ["Overview", "Key Points"],
        },
        "escalation": {
            "directory": "escalations",
            "filename_pattern": "{date}-{slug}.md",
            "sections": ["Summary", "Trigger", "Resolution"],
        },
        "entity": {
            "directory": "entities",
            "filename_pattern": "{slug}.md",
            "sections": ["Overview", "Details"],
        },
        "trend": {
            "directory": "trends",
            "filename_pattern": "{date}-{slug}.md",
            "sections": ["Summary", "Data", "Outlook"],
        },
    },
}

DEPARTMENTS_CONFIG = {
    "version": "1.0",
    "departments": {
        "cac": {
            "name": "Capital Allocation Committee",
            "shortName": "CAC",
            "dataAccess": {
                "wikiCollection": "cac_knowledge",
                "qdrantCollections": ["cac_docs", "cac_chat", "cac_knowledge"],
                "mirrorPaths": ["/data/mirror/alco/"],
                "excelFiles": ["ALCO_Tracker.xlsx"],
            },
        }
    },
    "globalAccess": {
        "roles": {"ceo": {"canRead": ["*"]}},
    },
}

COMPILE_EVENT_PAYLOAD = {
    "event_type": "proposal_approved",
    "dept_id": "cac",
    "payload": {
        "proposal_id": "chg_0001",
        "file": "ALCO_Tracker.xlsx",
        "tab": "Funding",
        "cell": "E8",
        "new_value": "3.15",
        "reasoning": "Rate adjustment per CAC decision.",
    },
    "source_id": "chg_0001",
}


# ---------------------------------------------------------------------------
# App factory — builds an isolated FastAPI app per test
# ---------------------------------------------------------------------------


def _build_test_app(tmp_path: Path) -> tuple[FastAPI, Path, MagicMock]:
    """
    Return (app, vault_path, mock_compiler) for one test.

    The app has its own lifespan that injects mocked/real components.
    WikiCompiler is replaced with a MagicMock; all IO helpers use tmp_path.
    """
    schema_path = tmp_path / "wiki_schema.json"
    schema_path.write_text(json.dumps(MINIMAL_SCHEMA))

    depts_path = tmp_path / "departments.json"
    depts_path.write_text(json.dumps(DEPARTMENTS_CONFIG))

    vault_path = tmp_path / "vault"
    vault_path.mkdir(exist_ok=True)

    import services.wiki_compiler.src.main as main_module
    from services.wiki_compiler.src.config import WikiSettings
    from services.wiki_compiler.src.dept_router import DeptRouter
    from services.wiki_compiler.src.index_manager import IndexManager
    from services.wiki_compiler.src.linker import Linker
    from services.wiki_compiler.src.log_writer import LogWriter

    settings = WikiSettings(
        wiki_schema_path=str(schema_path),
        departments_config=str(depts_path),
        vault_path=str(vault_path),
    )

    dept_router = DeptRouter(settings)
    index_manager = IndexManager(vault_path)
    log_writer = LogWriter(vault_path)
    linker = Linker(vault_path)
    mock_compiler = MagicMock()

    @contextlib.asynccontextmanager
    async def _test_lifespan(app: FastAPI):
        from services.wiki_compiler.src.linter import WikiLinter

        app.state.settings = settings
        app.state.compiler = mock_compiler
        app.state.dept_router = dept_router
        app.state.index_manager = index_manager
        app.state.log_writer = log_writer
        app.state.linker = linker
        app.state.linter = WikiLinter(vault_path=vault_path, linker=linker)
        yield

    # Build a fresh FastAPI app that reuses main's routes but with test lifespan
    from fastapi import FastAPI as _FastAPI
    test_app = _FastAPI(
        title="Wiki Compiler Test",
        version="0.1.0",
        lifespan=_test_lifespan,
    )
    # Copy all routes from the main app
    for route in main_module.app.routes:
        test_app.routes.append(route)

    return test_app, vault_path, mock_compiler


def _make_fake_article():
    """Build a minimal valid WikiArticle for cac/decisions/."""
    from services.wiki_compiler.src.models import ArticleFrontmatter, WikiArticle

    return WikiArticle(
        frontmatter=ArticleFrontmatter(
            title="Funding Rate Decision",
            type="decision",
            department="cac",
            sources=["chg_0001"],
            related=[],
            created="2026-04-07",
            updated="2026-04-07",
            confidence="high",
            coverage="medium",
            tags=[],
            ticket_id="chg_0001",
        ),
        body="## Summary\n\nThe funding rate was adjusted to 3.15%.\n",
        file_path="cac/decisions/2026-04-07-chg_0001.md",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_setup(tmp_path: Path):
    """Return (TestClient, vault_path, mock_compiler) for the test."""
    app, vault_path, mock_compiler = _build_test_app(tmp_path)
    with TestClient(app) as client:
        yield client, vault_path, mock_compiler


# ---------------------------------------------------------------------------
# 1. GET /health returns 200 with service name
# ---------------------------------------------------------------------------


def test_health_returns_200(test_setup) -> None:
    client, _, __ = test_setup
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "wiki-compiler"
    assert body["status"] == "healthy"


# ---------------------------------------------------------------------------
# 2. GET /health returns version
# ---------------------------------------------------------------------------


def test_health_returns_version(test_setup) -> None:
    client, _, __ = test_setup
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# 3. POST /compile with valid event returns compiled status
# ---------------------------------------------------------------------------


def test_compile_valid_event_returns_compiled(test_setup) -> None:
    client, vault_path, mock_compiler = test_setup
    mock_compiler.compile_event = AsyncMock(return_value=_make_fake_article())

    resp = client.post("/compile", json=COMPILE_EVENT_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "compiled"
    assert "article_path" in body


# ---------------------------------------------------------------------------
# 4. POST /compile writes article to disk
# ---------------------------------------------------------------------------


def test_compile_writes_article_to_disk(test_setup) -> None:
    client, vault_path, mock_compiler = test_setup
    mock_compiler.compile_event = AsyncMock(return_value=_make_fake_article())

    resp = client.post("/compile", json=COMPILE_EVENT_PAYLOAD)

    assert resp.status_code == 200
    assert resp.json()["status"] == "compiled"

    written_files = list(vault_path.rglob("*.md"))
    assert len(written_files) >= 1
    # The article itself lands under decisions/
    decision_files = [f for f in written_files if "decisions" in str(f)]
    assert len(decision_files) == 1
    assert "3.15" in decision_files[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. POST /compile with invalid dept_id returns error status
# ---------------------------------------------------------------------------


def test_compile_invalid_dept_returns_error(test_setup) -> None:
    client, vault_path, mock_compiler = test_setup

    bad_event = {
        "event_type": "proposal_approved",
        "dept_id": "nonexistent_dept",
        "payload": {"key": "value"},
        "source_id": "chg_9999",
    }

    from services.wiki_compiler.src.models import ArticleFrontmatter, WikiArticle

    bad_article = WikiArticle(
        frontmatter=ArticleFrontmatter(
            title="Bad Dept Article",
            type="decision",
            department="nonexistent_dept",
            sources=[],
            related=[],
            created="2026-04-07",
            updated="2026-04-07",
            confidence="low",
            coverage="low",
            tags=[],
        ),
        body="Some body.",
        file_path="nonexistent_dept/decisions/2026-04-07-chg_9999.md",
    )
    mock_compiler.compile_event = AsyncMock(return_value=bad_article)

    resp = client.post("/compile", json=bad_event)

    assert resp.status_code == 200
    # DeptRouter.resolve_vault_path raises ValueError for unknown dept
    assert resp.json()["status"] == "error"


# ---------------------------------------------------------------------------
# 6. POST /lint returns lint report
# ---------------------------------------------------------------------------


def test_lint_returns_report(test_setup) -> None:
    client, _, __ = test_setup
    resp = client.post("/lint", json={"dept_id": "cac"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["dept_id"] == "cac"
    assert "results" in body
    assert "articles_scanned" in body
