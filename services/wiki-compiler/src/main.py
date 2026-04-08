"""wiki-compiler service — FastAPI app for compiling events into wiki articles."""
from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import FastAPI, Request

from .compiler import WikiCompiler
from .config import WikiSettings
from .dept_router import DeptRouter
from .index_manager import IndexManager
from .linker import Linker
from .linter import WikiLinter
from .log_writer import LogWriter
from .models import CompileEvent, CompileResponse

logger = structlog.get_logger("wiki-compiler")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise service components on startup; clean up on shutdown."""
    settings = WikiSettings()

    compiler = WikiCompiler(settings)
    dept_router = DeptRouter(settings)
    index_manager = IndexManager(Path(settings.vault_path))
    log_writer = LogWriter(Path(settings.vault_path))
    linker = Linker(Path(settings.vault_path))

    app.state.settings = settings
    app.state.compiler = compiler
    app.state.dept_router = dept_router
    app.state.index_manager = index_manager
    app.state.log_writer = log_writer
    app.state.linker = linker
    app.state.linter = WikiLinter(vault_path=Path(settings.vault_path), linker=linker)

    logger.info("wiki-compiler.startup", port=settings.wiki_compiler_port)
    yield
    logger.info("wiki-compiler.shutdown")


app = FastAPI(
    title="Wiki Compiler",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"service": "wiki-compiler", "status": "healthy", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------


@app.post("/compile", response_model=CompileResponse)
async def compile_event(request: Request, event: CompileEvent) -> CompileResponse:
    """Compile a CompileEvent into a wiki article and write it to the vault."""
    state = request.app.state
    dept_router: DeptRouter = state.dept_router
    compiler: WikiCompiler = state.compiler
    index_manager: IndexManager = state.index_manager
    log_writer: LogWriter = state.log_writer
    linker: Linker = state.linker

    try:
        # 1. Compile the event via LLM
        article = await compiler.compile_event(event)

        # 2. Resolve the target file path
        slug = event.source_id or event.dept_id
        date = datetime.now(tz=UTC).date().isoformat()
        path = dept_router.resolve_vault_path(
            event.dept_id,
            article.frontmatter.type,
            slug,
            date,
        )

        # 3. Validate that the resolved path is inside the vault
        if not dept_router.validate_write_path(path):
            return CompileResponse(
                status="error",
                reason=f"Resolved path {path} is outside the configured vault.",
            )

        # 4. Write the article to disk
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(article.to_markdown(), encoding="utf-8")
        logger.info("wiki-compiler.compile.written", path=str(path))

        # 5. Update the department index
        index_manager.update_index(event.dept_id, article)

        # 6. Update backlinks in referenced articles
        pages_updated = linker.update_backlinks(event.dept_id, article)

        # 7. Append a log entry
        settings: WikiSettings = state.settings
        vault_path = Path(settings.vault_path)
        try:
            relative_path = str(path.relative_to(vault_path))
        except ValueError:
            relative_path = str(path)

        description = (
            f"Compiled {event.event_type} for {event.dept_id}"
            + (f" — source: {event.source_id}" if event.source_id else "")
        )
        log_writer.append_entry(event.dept_id, "ingest", description, pages_updated)

        return CompileResponse(
            status="compiled",
            article_path=relative_path,
            pages_updated=pages_updated,
        )

    except Exception as exc:
        logger.error("wiki-compiler.compile.failed", error=str(exc))
        return CompileResponse(status="error", reason=str(exc))


# ---------------------------------------------------------------------------
# Lint (placeholder — wired to linter in Task 11)
# ---------------------------------------------------------------------------


@app.post("/lint")
async def lint(request: Request, body: dict) -> dict:
    """Run the wiki health linter for a department and write a lint-report.md."""
    dept_id = body.get("dept_id", "cac")
    linter: WikiLinter = request.app.state.linter
    report = linter.lint_department(dept_id)
    linter.write_lint_report(dept_id, report)
    return report.model_dump()


if __name__ == "__main__":
    import uvicorn

    settings = WikiSettings()
    uvicorn.run(app, host="0.0.0.0", port=settings.wiki_compiler_port)
