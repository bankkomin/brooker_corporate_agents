"""Tests for wiki-compiler core compilation logic."""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: F401

import pytest

# Ensure langchain stubs are in sys.modules before conftest path hacking
# can shadow the real packages with service src/ directories.
if "langchain_openai" not in sys.modules:
    _mock_lc = MagicMock()
    sys.modules.setdefault("langchain_openai", _mock_lc)
    sys.modules.setdefault("langchain_core", MagicMock())
    sys.modules.setdefault("langchain_core.messages", MagicMock())
    sys.modules.setdefault("langchain_core.language_models", MagicMock())

from services.wiki_compiler.src.compiler import WikiCompiler
from services.wiki_compiler.src.config import WikiSettings
from services.wiki_compiler.src.models import CompileEvent, WikiArticle

# ---------------------------------------------------------------------------
# Shared fixtures
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
    },
    "compilation": {
        "model": "qwen-test",
        "temperature": 0.3,
        "max_tokens": 1024,
    },
}


@pytest.fixture
def schema_file(tmp_path: Path) -> Path:
    """Write minimal schema to a temp file and return its path."""
    p = tmp_path / "wiki_schema.json"
    p.write_text(json.dumps(MINIMAL_SCHEMA))
    return p


@pytest.fixture
def settings(schema_file: Path) -> WikiSettings:
    return WikiSettings(
        vllm_base_url="http://localhost:8000/v1",
        vllm_model="qwen-test",
        wiki_schema_path=str(schema_file),
        vault_path="/tmp/vault",
    )


@pytest.fixture
def compiler(settings: WikiSettings) -> WikiCompiler:
    return WikiCompiler(settings)


@pytest.fixture
def proposal_event() -> CompileEvent:
    return CompileEvent(
        event_type="proposal_approved",
        dept_id="cac",
        payload={
            "proposal_id": "chg_0001",
            "file": "ALCO_Tracker.xlsx",
            "tab": "Funding",
            "cell": "E8",
            "new_value": "3.15",
            "reasoning": "Rate adjustment per CAC decision.",
        },
        source_id="chg_0001",
    )


SAMPLE_MARKDOWN = textwrap.dedent("""\
    ---
    title: Funding Rate Decision
    type: decision
    department: cac
    sources:
    - chg_0001
    related: []
    created: '2026-04-07'
    updated: '2026-04-07'
    confidence: high
    coverage: medium
    tags: []
    ticket_id: chg_0001
    ---

    ## Summary

    The funding rate was adjusted to 3.15%.
""")


# ---------------------------------------------------------------------------
# 1. __init__ loads schema correctly
# ---------------------------------------------------------------------------

def test_init_loads_schema(compiler: WikiCompiler) -> None:
    assert "decision" in compiler.schema["article_types"]
    assert "concept" in compiler.schema["article_types"]


# ---------------------------------------------------------------------------
# 2. _build_system_prompt includes article type sections
# ---------------------------------------------------------------------------

def test_build_system_prompt_contains_sections(compiler: WikiCompiler) -> None:
    prompt = compiler._build_system_prompt("decision")
    assert "Summary" in prompt
    assert "Change Details" in prompt
    assert "Rationale" in prompt


def test_build_system_prompt_unknown_type_uses_generic(compiler: WikiCompiler) -> None:
    prompt = compiler._build_system_prompt("nonexistent_type")
    # Should still return a non-empty prompt rather than crash
    assert isinstance(prompt, str)
    assert len(prompt) > 10


# ---------------------------------------------------------------------------
# 3. _build_user_prompt formats event payload
# ---------------------------------------------------------------------------

def test_build_user_prompt_includes_payload_fields(
    compiler: WikiCompiler, proposal_event: CompileEvent
) -> None:
    prompt = compiler._build_user_prompt(proposal_event)
    assert "chg_0001" in prompt
    assert "cac" in prompt
    assert "proposal_approved" in prompt


# ---------------------------------------------------------------------------
# 4. compile_event with mocked LLM returns valid WikiArticle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compile_event_returns_wiki_article(
    compiler: WikiCompiler, proposal_event: CompileEvent
) -> None:
    mock_response = MagicMock()
    mock_response.content = SAMPLE_MARKDOWN

    with patch.object(compiler, "_call_llm", new=AsyncMock(return_value=SAMPLE_MARKDOWN)):
        article = await compiler.compile_event(proposal_event)

    assert isinstance(article, WikiArticle)
    assert article.frontmatter.title == "Funding Rate Decision"
    assert article.frontmatter.department == "cac"
    assert "3.15" in article.body


# ---------------------------------------------------------------------------
# 5. _parse_response with frontmatter markdown
# ---------------------------------------------------------------------------

def test_parse_response_with_frontmatter(
    compiler: WikiCompiler, proposal_event: CompileEvent
) -> None:
    article = compiler._parse_response(SAMPLE_MARKDOWN, proposal_event)
    assert isinstance(article, WikiArticle)
    assert article.frontmatter.title == "Funding Rate Decision"
    assert article.frontmatter.type == "decision"
    assert article.frontmatter.confidence == "high"
    assert "Summary" in article.body


# ---------------------------------------------------------------------------
# 6. _parse_response with raw text (no frontmatter)
# ---------------------------------------------------------------------------

def test_parse_response_with_raw_text(
    compiler: WikiCompiler, proposal_event: CompileEvent
) -> None:
    raw = "The funding rate was adjusted to 3.15% following CAC approval."
    article = compiler._parse_response(raw, proposal_event)
    assert isinstance(article, WikiArticle)
    # Frontmatter must be constructed from event metadata
    assert article.frontmatter.department == "cac"
    assert raw in article.body


# ---------------------------------------------------------------------------
# 7. compile_event sets article_type based on event_type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compile_event_article_type_from_event(
    compiler: WikiCompiler, proposal_event: CompileEvent
) -> None:
    raw_body = "Rate was changed."
    with patch.object(compiler, "_call_llm", new=AsyncMock(return_value=raw_body)):
        article = await compiler.compile_event(proposal_event)

    # proposal_approved maps to "decision"
    assert article.frontmatter.type == "decision"


# ---------------------------------------------------------------------------
# 8. Error handling when LLM call fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compile_event_llm_failure_raises(
    compiler: WikiCompiler, proposal_event: CompileEvent
) -> None:
    with patch.object(
        compiler, "_call_llm", new=AsyncMock(side_effect=RuntimeError("vLLM unreachable"))
    ), pytest.raises(RuntimeError, match="vLLM unreachable"):
        await compiler.compile_event(proposal_event)
