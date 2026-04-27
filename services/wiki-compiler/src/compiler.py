"""Core wiki compilation — transforms events into structured wiki articles."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from .config import WikiSettings
from .models import ArticleFrontmatter, ArticleType, CompileEvent, WikiArticle

logger = structlog.get_logger("wiki-compiler.compiler")

# ---------------------------------------------------------------------------
# Event-type → article-type mapping
# ---------------------------------------------------------------------------

_EVENT_TO_ARTICLE_TYPE: dict[str, ArticleType] = {
    "proposal_approved": "decision",
    "document_ingested": "source-summary",
    "slack_digest": "meeting-note",
    "escalation_triggered": "escalation",
    "lint_request": "concept",
}

# Fallback article type when no mapping exists
_DEFAULT_ARTICLE_TYPE: ArticleType = "concept"


class WikiCompiler:
    """Transforms CompileEvents into WikiArticles via an LLM."""

    def __init__(self, settings: WikiSettings) -> None:
        self._settings = settings
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        self._llm = ChatOpenAI(
            base_url=settings.vllm_base_url,
            api_key="not-needed",  # vLLM does not require an API key
            model=settings.vllm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            request_timeout=180,
            max_retries=3,
        )
        schema_path = Path(settings.wiki_schema_path)
        self.schema: dict[str, Any] = json.loads(schema_path.read_text())
        logger.info(
            "WikiCompiler initialised",
            schema_path=str(schema_path),
            article_types=list(self.schema.get("article_types", {}).keys()),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compile_event(self, event: CompileEvent) -> WikiArticle:
        """Main entry point: compile a CompileEvent into a WikiArticle."""
        article_type = _EVENT_TO_ARTICLE_TYPE.get(event.event_type, _DEFAULT_ARTICLE_TYPE)
        logger.info(
            "Compiling wiki article",
            event_type=event.event_type,
            article_type=article_type,
            dept_id=event.dept_id,
        )

        system_prompt = self._build_system_prompt(article_type)
        user_prompt = self._build_user_prompt(event)

        try:
            raw = await self._call_llm(system_prompt, user_prompt)
        except Exception:
            logger.error(
                "WikiCompiler.compile_event LLM call failed",
                event_type=event.event_type,
                article_type=article_type,
                dept_id=event.dept_id,
                source_id=event.source_id,
            )
            raise
        article = self._parse_response(raw, event)
        logger.info("Compiled wiki article", file_path=article.file_path)
        return article

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_system_prompt(self, article_type: str) -> str:
        """Build a system prompt for the given article type using the schema."""
        article_types: dict[str, Any] = self.schema.get("article_types", {})
        article_spec = article_types.get(article_type)

        if article_spec:
            sections = article_spec.get("sections", [])
            section_list = "\n".join(f"- ## {s}" for s in sections)
            return (
                "You are a professional knowledge-base writer for a financial institution.\n"
                f"Write a wiki article of type '{article_type}'.\n"
                "The article MUST use the following Markdown sections in order:\n"
                f"{section_list}\n\n"
                "Return the article as a Markdown file with YAML frontmatter delimited by ---.\n"
                "The frontmatter must include: title, type, department, sources, related, "
                "created, updated, confidence, coverage, tags, ticket_id.\n"
                "Use ISO date format (YYYY-MM-DD) for date fields.\n"
                "Be concise, factual, and citation-driven."
            )

        # Generic fallback for unknown types
        return (
            "You are a professional knowledge-base writer for a financial institution.\n"
            "Write a wiki article based on the provided information.\n"
            "Return the article as a Markdown file with YAML frontmatter delimited by ---.\n"
            "The frontmatter must include: title, type, department, sources, related, "
            "created, updated, confidence, coverage, tags, ticket_id.\n"
            "Use ISO date format (YYYY-MM-DD) for date fields."
        )

    def _build_user_prompt(self, event: CompileEvent) -> str:
        """Format an event into the user message sent to the LLM."""
        payload_json = json.dumps(event.payload, indent=2, ensure_ascii=False)
        return (
            f"Event type: {event.event_type}\n"
            f"Department: {event.dept_id}\n"
            f"Timestamp: {event.timestamp}\n"
            f"Source ID: {event.source_id}\n\n"
            f"Payload:\n{payload_json}"
        )

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Invoke the LLM and return the raw string content."""
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

        try:
            response = await self._llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
        except Exception:
            logger.exception(
                "WikiCompiler._call_llm failed",
                model=self._settings.vllm_model,
                base_url=self._settings.vllm_base_url,
            )
            raise
        return str(response.content)

    # ------------------------------------------------------------------
    # Response parser
    # ------------------------------------------------------------------

    def _parse_response(self, raw: str, event: CompileEvent) -> WikiArticle:
        """Parse the LLM response into a WikiArticle.

        Handles two cases:
        1. LLM returned markdown with ``---`` frontmatter delimiters.
        2. LLM returned raw text without frontmatter → construct frontmatter
           from event metadata.
        """
        article_type: ArticleType = _EVENT_TO_ARTICLE_TYPE.get(
            event.event_type, _DEFAULT_ARTICLE_TYPE
        )
        today = datetime.now(tz=UTC).date().isoformat()

        # Determine file_path from schema or a sensible default
        article_spec = self.schema.get("article_types", {}).get(article_type, {})
        directory = article_spec.get("directory", article_type)
        slug = event.source_id or event.dept_id
        file_path = f"{event.dept_id}/{directory}/{today}-{slug}.md"

        # Case 1: well-formed frontmatter
        if raw.startswith("---"):
            try:
                return WikiArticle.from_markdown(raw, file_path=file_path)
            except (ValueError, KeyError):
                logger.warning(
                    "Failed to parse frontmatter, falling back to raw-text path",
                    event_type=event.event_type,
                )

        # Case 2: raw text — construct minimal frontmatter
        source_id = event.source_id or ""
        frontmatter = ArticleFrontmatter(
            title=f"{event.event_type.replace('_', ' ').title()} — {event.dept_id}",
            type=article_type,
            department=event.dept_id,
            sources=[source_id] if source_id else [],
            related=[],
            created=today,
            updated=today,
            confidence="low",
            coverage="low",
            tags=[],
            ticket_id=source_id or None,
        )
        return WikiArticle(frontmatter=frontmatter, body=raw, file_path=file_path)
