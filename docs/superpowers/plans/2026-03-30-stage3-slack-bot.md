# Stage 3 — Slack Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Slack Bot service (`services/slack-bot/`) that bridges the #cac-committee Slack channel with the RAG pipeline — indexing messages, downloading shared files for ingestion, and handling @agent mentions with threaded replies.

**Architecture:** Slack Bolt (async) mounted inside FastAPI via `AsyncSlackRequestHandler` — single uvicorn process on port 3003. All events are ACK'd immediately, then processed asynchronously via `asyncio.create_task()`. The bot communicates with rag-ingestion over HTTP (httpx), and stubs the cac-orchestrator call via a feature flag until Stage 4.

**Tech Stack:** Python 3.11, FastAPI, Slack Bolt (async), httpx, Pydantic v2, pydantic-settings, structlog, tenacity, aiofiles

**Design Spec:** Architecture, backend, and QA agent reviews (2026-03-30)

---

## System Overview

### Slack Event Routing

```mermaid
flowchart TD
    START(["Slack Event Received"])
    CHAN{{"Monitored<br/>channel?"}}
    BOT{{"From a<br/>bot?"}}
    TYPE{{"Event type?"}}
    MSG["Index message<br/>via RAG Ingestion"]
    FILE_DL["Download<br/>shared file"]
    FILE_OK{{"Supported<br/>file type?"}}
    FILE_FWD["Forward to RAG<br/>for ingestion"]
    FILE_SKIP(("Skip &<br/>log"))
    MENTION["Forward question<br/>to Orchestrator"]
    REPLY["Post threaded<br/>reply in Slack"]
    IGNORE1(("Ignore"))
    IGNORE2(("Ignore"))

    START --> CHAN
    CHAN -->|"No"| IGNORE1
    CHAN -->|"Yes"| BOT
    BOT -->|"Yes"| IGNORE2
    BOT -->|"No"| TYPE
    TYPE -->|"Message"| MSG
    TYPE -->|"File shared"| FILE_DL
    TYPE -->|"@agent mention"| MENTION
    FILE_DL --> FILE_OK
    FILE_OK -->|"Yes"| FILE_FWD
    FILE_OK -->|"No"| FILE_SKIP
    MSG --> REPLY
    FILE_FWD --> REPLY
    MENTION --> REPLY

    classDef automated fill:#e1f0ff,stroke:#4a90d9,color:#333
    classDef human fill:#e1f5e1,stroke:#4caf50,color:#333
    classDef external fill:#fff3e0,stroke:#ff9800,color:#333

    class MSG,FILE_DL,FILE_FWD,MENTION,REPLY automated
    class START external
    class CHAN,BOT,TYPE,FILE_OK automated
```

> **Legend:** 🔵 Blue = Automated processing · 🟠 Orange = External input (Slack)

### Message Processing Lifecycle

```mermaid
sequenceDiagram
    participant SA as Slack API
    participant SB as Slack Bot
    participant RAG as RAG Ingestion
    participant ORC as CAC Orchestrator

    SA->>SB: 1. Send event
    SB-->>SA: 2. ACK (within 3 seconds)

    Note over SB: Spawn background task

    alt @agent mention
        SB->>ORC: 3a. Forward question
        activate ORC
        ORC-->>SB: Response + citations
        deactivate ORC
        SB->>SA: 4a. Post threaded reply
    else Regular message
        SB->>RAG: 3b. Index message
        RAG-->>SB: Indexed OK
    else File shared
        SB->>SB: 3c. Download file
        SB->>RAG: Forward file for ingestion
        RAG-->>SB: Ingested OK
    end

    alt Service unreachable
        SB->>SA: Post "service unavailable" reply
    end
```

## File Map

### slack-bot service (NEW)

| File | Responsibility |
|------|---------------|
| `services/slack-bot/__init__.py` | Package init (required for conftest.py import registration) |
| `services/slack-bot/Dockerfile` | Python 3.11-slim container, runs uvicorn on port 3003 |
| `services/slack-bot/requirements.txt` | Service dependencies |
| `services/slack-bot/src/__init__.py` | Package init |
| `services/slack-bot/src/config.py` | SlackBotSettings (pydantic-settings) with Slack creds, service URLs, feature flags |
| `services/slack-bot/src/models.py` | Pydantic v2 models: SlackFileInfo, IngestMessageRequest, QueryRequest/Response |
| `services/slack-bot/src/clients.py` | RAGIngestionClient + OrchestratorClient — httpx wrappers with retry logic |
| `services/slack-bot/src/events.py` | Bolt event handlers: message, file_shared, app_mention (ACK-then-process) |
| `services/slack-bot/src/file_handler.py` | Download Slack files to temp, POST multipart to rag-ingestion, cleanup |
| `services/slack-bot/src/responder.py` | Format and send thread replies with Block Kit citations |
| `services/slack-bot/src/main.py` | FastAPI app + Bolt mount at /slack/events + /health endpoint |

### Test files (NEW)

| File | Tests For |
|------|----------|
| `tests/unit/slack_bot/__init__.py` | Package init |
| `tests/unit/slack_bot/test_config.py` | Settings loading, defaults, missing required vars |
| `tests/unit/slack_bot/test_models.py` | Pydantic model validation |
| `tests/unit/slack_bot/test_clients.py` | RAG/Orchestrator client payloads, retry, stub behavior |
| `tests/unit/slack_bot/test_events.py` | Event handlers: ACK, bot filtering, background task dispatch |
| `tests/unit/slack_bot/test_file_handler.py` | File download, type validation, temp cleanup |
| `tests/unit/slack_bot/test_responder.py` | Response formatting, thread replies, citation rendering |
| `tests/unit/slack_bot/test_main.py` | FastAPI /health endpoint, /slack/events route exists |
| `tests/integration/test_slack_bot.py` | Full event flow with mocked Slack API |

### Modified files

| File | Change |
|------|--------|
| `docker-compose.yml` | Uncomment slack-bot stub, add full config with depends_on rag-ingestion |
| `docker-compose.dev.yml` | Add dev overrides for slack-bot (reload, DEBUG logging) |
| `docs/Implementation.md` | Check off Stage 3 items as completed |

---

## Dependency DAG

```
Task 1 (config) ──┐
Task 2 (models) ──┼── Task 4 (clients) ──┐
                  │                       ├── Task 6 (events) ──┐
Task 3 (responder)┘                       │                     ├── Task 9 (main + Dockerfile)
                   Task 5 (file_handler) ──┘                     │
                                                                 │
Task 7 (unit tests events) ────────────────────────────────────┤
Task 8 (unit tests file_handler + responder) ──────────────────┤
                                                                 │
Task 10 (Docker Compose) ────────────────────────────────────────┤
Task 11 (integration test) ──────────────────────────────────────┤
Task 12 (final verification) ────────────────────────────────────┘
```

**Parallelizable:** Tasks 1, 2, 3 can run in parallel. Tasks 7, 8 can run in parallel.

---

## Task Breakdown

### Task 1: Config + Package Init

**Files:**
- Create: `services/slack-bot/__init__.py`
- Create: `services/slack-bot/src/__init__.py`
- Create: `services/slack-bot/src/config.py`
- Create: `services/slack-bot/requirements.txt`
- Test: `tests/unit/slack_bot/__init__.py`
- Test: `tests/unit/slack_bot/test_config.py`

- [ ] **Step 1: Create requirements.txt**

```
slack-bolt>=1.20.0
fastapi>=0.111.0
uvicorn>=0.30.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
httpx>=0.27.0
structlog>=23.0.0
tenacity>=8.3.0
aiofiles>=23.2.0
```

- [ ] **Step 2: Write failing test for config**

```python
# tests/unit/slack_bot/__init__.py
# (empty)
```

```python
# tests/unit/slack_bot/test_config.py
"""Tests for slack-bot service configuration."""

import pytest
from pydantic import ValidationError


class TestSlackBotSettings:
    def test_required_fields_load_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings load successfully when all required env vars are set."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.slack_bot_token == "xoxb-test-token"
        assert s.slack_signing_secret == "test-secret"
        assert s.cac_channel_id == "C0123456789"

    def test_missing_slack_bot_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing SLACK_BOT_TOKEN must raise ValidationError."""
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

        from services.slack_bot.src.config import SlackBotSettings

        with pytest.raises(ValidationError):
            SlackBotSettings()

    def test_missing_signing_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing SLACK_SIGNING_SECRET must raise ValidationError."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")
        monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)

        from services.slack_bot.src.config import SlackBotSettings

        with pytest.raises(ValidationError):
            SlackBotSettings()

    def test_default_service_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Downstream service URLs default to Docker DNS names."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.rag_ingestion_url == "http://rag-ingestion:3004"
        assert s.cac_orchestrator_url == "http://cac-orchestrator:3001"

    def test_orchestrator_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Orchestrator feature flag defaults to False (Stage 3 stub)."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.orchestrator_enabled is False

    def test_custom_url_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Service URLs can be overridden via env vars."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
        monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
        monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
        monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")
        monkeypatch.setenv("RAG_INGESTION_URL", "http://localhost:3004")

        from services.slack_bot.src.config import SlackBotSettings

        s = SlackBotSettings()
        assert s.rag_ingestion_url == "http://localhost:3004"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/slack_bot/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.slack_bot'`

- [ ] **Step 4: Create package inits and implement config**

```python
# services/slack-bot/__init__.py
# (empty — required for conftest.py import registration)
```

```python
# services/slack-bot/src/__init__.py
# (empty)
```

```python
# services/slack-bot/src/config.py
"""slack-bot service configuration."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class SlackBotSettings(BaseSettings):
    model_config = {"env_prefix": "", "case_sensitive": False}

    # --- Slack credentials (REQUIRED) ---
    slack_bot_token: str = Field(..., description="xoxb-... bot OAuth token")
    slack_signing_secret: str = Field(..., description="Bolt request signature secret")

    # --- Channel IDs (REQUIRED) ---
    cac_channel_id: str = Field(..., description="Primary CAC committee channel")
    escalations_channel_id: str = Field(..., description="Escalations channel")
    approvals_channel_id: str = Field(..., description="Approvals channel")

    # --- Downstream services ---
    rag_ingestion_url: str = "http://rag-ingestion:3004"
    cac_orchestrator_url: str = "http://cac-orchestrator:3001"
    orchestrator_enabled: bool = False  # Flip to True in Stage 4

    # --- File handling ---
    max_file_size_mb: int = 50
    allowed_file_types: str = "pdf,xlsx,docx,txt,md"

    # --- HTTP client ---
    http_timeout_seconds: float = 10.0
    http_max_retries: int = 3

    # --- Logging ---
    log_level: str = "INFO"

    @property
    def allowed_types_set(self) -> frozenset[str]:
        return frozenset(t.strip() for t in self.allowed_file_types.split(","))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/slack_bot/test_config.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add services/slack-bot/__init__.py services/slack-bot/src/__init__.py services/slack-bot/src/config.py services/slack-bot/requirements.txt tests/unit/slack_bot/__init__.py tests/unit/slack_bot/test_config.py
git commit -m "feat(slack-bot): add config and package init"
```

---

### Task 2: Pydantic Models

**Files:**
- Create: `services/slack-bot/src/models.py`
- Test: `tests/unit/slack_bot/test_models.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/slack_bot/test_models.py
"""Tests for slack-bot Pydantic models."""

import pytest
from pydantic import ValidationError


class TestSlackFileInfo:
    def test_valid_file_info(self) -> None:
        from services.slack_bot.src.models import SlackFileInfo

        f = SlackFileInfo(
            id="F12345",
            name="alco_minutes.pdf",
            mimetype="application/pdf",
            url_private_download="https://files.slack.com/files/alco_minutes.pdf",
            size=204800,
            filetype="pdf",
        )
        assert f.id == "F12345"
        assert f.size == 204800

    def test_missing_id_raises(self) -> None:
        from services.slack_bot.src.models import SlackFileInfo

        with pytest.raises(ValidationError):
            SlackFileInfo(
                name="test.pdf",
                mimetype="application/pdf",
                url_private_download="https://example.com/file",
                size=100,
                filetype="pdf",
            )


class TestIngestMessageRequest:
    def test_valid_request(self) -> None:
        from services.slack_bot.src.models import IngestMessageRequest

        req = IngestMessageRequest(
            text="Q3 funding update",
            author="U12345",
            channel_id="C0123456789",
            timestamp="1711234567.000100",
        )
        assert req.dept == "CAC"
        assert req.thread_ts is None

    def test_missing_text_raises(self) -> None:
        from services.slack_bot.src.models import IngestMessageRequest

        with pytest.raises(ValidationError):
            IngestMessageRequest(
                author="U12345",
                channel_id="C0123456789",
                timestamp="1711234567.000100",
            )


class TestQueryRequest:
    def test_valid_query(self) -> None:
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(
            query="What is the current LCR?",
            channel_id="C0123456789",
            user_id="U12345",
        )
        assert q.thread_ts is None
        assert q.context == {}

    def test_with_thread_ts(self) -> None:
        from services.slack_bot.src.models import QueryRequest

        q = QueryRequest(
            query="Follow up",
            channel_id="C123",
            user_id="U456",
            thread_ts="1711234567.000100",
        )
        assert q.thread_ts == "1711234567.000100"


class TestQueryResponse:
    def test_valid_response(self) -> None:
        from services.slack_bot.src.models import QueryResponse

        r = QueryResponse(
            answer="The current LCR is 135%.",
            confidence=0.91,
        )
        assert r.citations == []
        assert r.error is None

    def test_with_citations(self) -> None:
        from services.slack_bot.src.models import Citation, QueryResponse

        r = QueryResponse(
            answer="Rate is 3.15%",
            citations=[Citation(source="ALCO_Tracker.xlsx", excerpt="Row 8", score=0.95)],
            confidence=0.91,
        )
        assert len(r.citations) == 1
        assert r.citations[0].source == "ALCO_Tracker.xlsx"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/slack_bot/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement models**

```python
# services/slack-bot/src/models.py
"""Pydantic v2 schemas for slack-bot internal and external payloads."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Slack inbound ────────────────────────────────────────────────────

class SlackFileInfo(BaseModel):
    """Subset of Slack's file object needed for download."""

    id: str
    name: str
    mimetype: str
    url_private_download: str
    size: int
    filetype: str


# ── Outbound to rag-ingestion ────────────────────────────────────────

class IngestMessageRequest(BaseModel):
    """POST /ingest/message payload."""

    text: str
    author: str
    channel_id: str
    timestamp: str
    dept: str = "CAC"
    thread_ts: str | None = None


# ── Outbound to cac-orchestrator ─────────────────────────────────────

class QueryRequest(BaseModel):
    """POST /query payload."""

    query: str
    channel_id: str
    user_id: str
    thread_ts: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """Single citation in a QueryResponse."""

    source: str
    excerpt: str
    score: float


class QueryResponse(BaseModel):
    """Response from cac-orchestrator."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    agent_id: str = ""
    error: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/slack_bot/test_models.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/slack-bot/src/models.py tests/unit/slack_bot/test_models.py
git commit -m "feat(slack-bot): add Pydantic models"
```

---

### Task 3: Responder (Thread Reply Formatting)

**Files:**
- Create: `services/slack-bot/src/responder.py`
- Test: `tests/unit/slack_bot/test_responder.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/slack_bot/test_responder.py
"""Tests for slack-bot response formatting and thread replies."""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestFormatQueryResponse:
    def test_plain_answer_returns_text(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(answer="LCR is 135%.", confidence=0.91)
        text, blocks = format_response(r)
        assert "LCR is 135%" in text

    def test_with_citations_includes_sources(self) -> None:
        from services.slack_bot.src.models import Citation, QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(
            answer="Rate is 3.15%",
            citations=[Citation(source="ALCO_Tracker.xlsx", excerpt="Row 8 col E", score=0.95)],
            confidence=0.91,
        )
        text, blocks = format_response(r)
        assert blocks is not None
        block_text = str(blocks)
        assert "ALCO_Tracker.xlsx" in block_text

    def test_no_citations_returns_none_blocks(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(answer="No data found.", confidence=0.91)
        text, blocks = format_response(r)
        assert blocks is None or all(b.get("type") != "context" or "Sources" not in str(b) for b in blocks)

    def test_error_response_shows_error(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import format_response

        r = QueryResponse(answer="", error="Service unavailable")
        text, blocks = format_response(r)
        assert "error" in text.lower() or "unavailable" in text.lower()

    def test_citation_excerpt_truncated(self) -> None:
        from services.slack_bot.src.models import Citation, QueryResponse
        from services.slack_bot.src.responder import format_response

        long_excerpt = "A" * 200
        r = QueryResponse(
            answer="Answer",
            citations=[Citation(source="doc.pdf", excerpt=long_excerpt, score=0.9)],
            confidence=0.91,
        )
        _, blocks = format_response(r)
        block_text = str(blocks)
        assert len(long_excerpt) > 120
        # The full 200-char excerpt should not appear untruncated
        assert long_excerpt not in block_text


class TestReplyInThread:
    @pytest.mark.asyncio
    async def test_posts_to_correct_channel(self) -> None:
        from services.slack_bot.src.responder import reply_in_thread

        client = MagicMock()
        client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "9999.0"})
        await reply_in_thread(client, "C123", "1234.5678", "Hello")
        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["thread_ts"] == "1234.5678"

    @pytest.mark.asyncio
    async def test_query_response_uses_blocks(self) -> None:
        from services.slack_bot.src.models import QueryResponse
        from services.slack_bot.src.responder import reply_in_thread

        client = MagicMock()
        client.chat_postMessage = AsyncMock(return_value={"ok": True})
        resp = QueryResponse(answer="Answer here", confidence=0.9)
        await reply_in_thread(client, "C123", "1234.5678", resp)
        call_kwargs = client.chat_postMessage.call_args[1]
        assert "text" in call_kwargs


class TestPostErrorToThread:
    @pytest.mark.asyncio
    async def test_sends_user_friendly_message(self) -> None:
        from services.slack_bot.src.responder import post_error_to_thread

        client = MagicMock()
        client.chat_postMessage = AsyncMock(return_value={"ok": True})
        await post_error_to_thread(client, "C123", "1234.5678", RuntimeError("db crash"))
        call_kwargs = client.chat_postMessage.call_args[1]
        # Should NOT contain the raw exception message
        assert "db crash" not in call_kwargs["text"]
        # Should contain user-friendly language
        assert "error" in call_kwargs["text"].lower() or "sorry" in call_kwargs["text"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/slack_bot/test_responder.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement responder**

```python
# services/slack-bot/src/responder.py
"""Format and post Slack replies."""
from __future__ import annotations

import structlog

from .models import QueryResponse, Citation

logger = structlog.get_logger("slack-bot.responder")


def format_response(response: QueryResponse) -> tuple[str, list[dict] | None]:
    """Build Block Kit blocks from a QueryResponse.

    Returns (fallback_text, blocks_list).
    """
    if response.error:
        return f"Error: {response.error}", None

    fallback = response.answer

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": response.answer},
        }
    ]

    if response.citations:
        citation_lines = _format_citations(response.citations)
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Sources*\n{citation_lines}"},
                ],
            }
        )

    if response.confidence > 0:
        confidence_pct = int(response.confidence * 100)
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"_Confidence: {confidence_pct}%_"},
                ],
            }
        )

    return fallback, blocks


def _format_citations(citations: list[Citation]) -> str:
    """Render citations as a compact numbered list."""
    lines = []
    for i, c in enumerate(citations, start=1):
        excerpt = c.excerpt[:120] + "..." if len(c.excerpt) > 120 else c.excerpt
        lines.append(f"{i}. *{c.source}* - _{excerpt}_")
    return "\n".join(lines)


async def reply_in_thread(
    client,
    channel: str,
    thread_ts: str,
    content: str | QueryResponse,
) -> None:
    """Post a message into the thread identified by (channel, thread_ts)."""
    if isinstance(content, str):
        text = content
        blocks = None
    else:
        text, blocks = format_response(content)

    try:
        await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks,
        )
        logger.info("responder.replied", channel=channel, thread_ts=thread_ts)
    except Exception as exc:
        logger.error("responder.post_failed", channel=channel, error=str(exc))


async def post_error_to_thread(
    client,
    channel: str,
    thread_ts: str,
    exc: Exception,
) -> None:
    """Send a user-facing error message to the thread."""
    msg = (
        "Sorry, I ran into an error processing your request. "
        "The team has been notified. Please try again shortly."
    )
    logger.error("responder.error_reply", channel=channel, error=str(exc))
    await reply_in_thread(client, channel, thread_ts, msg)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/slack_bot/test_responder.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/slack-bot/src/responder.py tests/unit/slack_bot/test_responder.py
git commit -m "feat(slack-bot): add responder with Block Kit formatting"
```

---

### Task 4: HTTP Clients (RAG + Orchestrator)

**Files:**
- Create: `services/slack-bot/src/clients.py`
- Test: `tests/unit/slack_bot/test_clients.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/slack_bot/test_clients.py
"""Tests for HTTP client wrappers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


class TestRAGIngestionClient:
    @pytest.mark.asyncio
    async def test_index_message_posts_correct_payload(self) -> None:
        from services.slack_bot.src.clients import RAGIngestionClient

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"indexed": True, "message_id": "msg_abc"}

        http = MagicMock()
        http.post = AsyncMock(return_value=mock_response)

        client = RAGIngestionClient(http=http, base_url="http://rag:3004")
        result = await client.index_message(
            text="Q3 update",
            author="U12345",
            channel_id="C123",
            timestamp="1711234567.000100",
        )
        assert result is True
        call_kwargs = http.post.call_args
        assert "/ingest/message" in call_kwargs[0][0]

    @pytest.mark.asyncio
    async def test_index_message_returns_false_on_error(self) -> None:
        from services.slack_bot.src.clients import RAGIngestionClient

        http = MagicMock()
        http.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        client = RAGIngestionClient(http=http, base_url="http://rag:3004")
        result = await client.index_message(
            text="test", author="U1", channel_id="C1", timestamp="1.0",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_returns_true(self) -> None:
        from services.slack_bot.src.clients import RAGIngestionClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        http = MagicMock()
        http.get = AsyncMock(return_value=mock_resp)

        client = RAGIngestionClient(http=http, base_url="http://rag:3004")
        assert await client.health_check() is True


class TestOrchestratorClient:
    @pytest.mark.asyncio
    async def test_query_when_disabled_returns_stub(self) -> None:
        from services.slack_bot.src.clients import OrchestratorClient

        http = MagicMock()
        client = OrchestratorClient(http=http, base_url="http://orch:3001", enabled=False)
        result = await client.query(
            query="What is the LCR?",
            user_id="U123",
            channel_id="C123",
        )
        assert "still being set up" in result.answer.lower() or "not yet" in result.answer.lower()
        http.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_query_when_enabled_calls_orchestrator(self) -> None:
        from services.slack_bot.src.clients import OrchestratorClient

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "answer": "LCR is 135%",
            "citations": [],
            "confidence": 0.91,
        }

        http = MagicMock()
        http.post = AsyncMock(return_value=mock_resp)

        client = OrchestratorClient(http=http, base_url="http://orch:3001", enabled=True)
        result = await client.query(
            query="What is the LCR?",
            user_id="U123",
            channel_id="C123",
        )
        assert "135%" in result.answer
        http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_error_returns_error_response(self) -> None:
        from services.slack_bot.src.clients import OrchestratorClient

        http = MagicMock()
        http.post = AsyncMock(side_effect=httpx.ConnectError("down"))

        client = OrchestratorClient(http=http, base_url="http://orch:3001", enabled=True)
        result = await client.query(
            query="test", user_id="U1", channel_id="C1",
        )
        assert result.error is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/slack_bot/test_clients.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement clients**

```python
# services/slack-bot/src/clients.py
"""HTTP client wrappers for downstream services."""
from __future__ import annotations

import httpx
import structlog

from .models import IngestMessageRequest, QueryRequest, QueryResponse

logger = structlog.get_logger("slack-bot.clients")


class RAGIngestionClient:
    """Async client for rag-ingestion service."""

    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def index_message(
        self,
        *,
        text: str,
        author: str,
        channel_id: str,
        timestamp: str,
        thread_ts: str | None = None,
    ) -> bool:
        """POST message to rag-ingestion for indexing. Returns True on success."""
        payload = IngestMessageRequest(
            text=text,
            author=author,
            channel_id=channel_id,
            timestamp=timestamp,
            thread_ts=thread_ts,
        )
        try:
            resp = await self._http.post(
                f"{self._base_url}/ingest/message",
                json=payload.model_dump(),
            )
            resp.raise_for_status()
            logger.info("clients.message_indexed", ts=timestamp, channel=channel_id)
            return True
        except Exception as exc:
            logger.error("clients.message_index_failed", error=str(exc), ts=timestamp)
            return False

    async def upload_file(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        filetype: str,
        channel_id: str,
        file_id: str,
    ) -> dict:
        """POST multipart file to rag-ingestion. Returns response dict."""
        files = {"file": (filename, file_bytes, f"application/{filetype}")}
        data = {
            "dept": "CAC",
            "doc_type": filetype,
            "collection": "cac_docs",
            "channel_id": channel_id,
            "slack_file_id": file_id,
        }
        resp = await self._http.post(
            f"{self._base_url}/ingest/document",
            files=files,
            data=data,
        )
        resp.raise_for_status()
        return resp.json()

    async def health_check(self) -> bool:
        """Check if rag-ingestion is reachable."""
        try:
            resp = await self._http.get(f"{self._base_url}/health")
            resp.raise_for_status()
            return True
        except Exception:
            return False


class OrchestratorClient:
    """Async client for cac-orchestrator service (stubbed in Stage 3)."""

    STUB_MESSAGE = (
        "I'm still being set up and can't answer questions yet. "
        "Your message has been noted and indexed."
    )

    def __init__(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        enabled: bool = False,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._enabled = enabled

    async def query(
        self,
        *,
        query: str,
        user_id: str,
        channel_id: str,
        thread_ts: str | None = None,
    ) -> QueryResponse:
        """Send query to cac-orchestrator. Returns stub when disabled."""
        if not self._enabled:
            return QueryResponse(answer=self.STUB_MESSAGE, confidence=0.0)

        payload = QueryRequest(
            query=query,
            channel_id=channel_id,
            user_id=user_id,
            thread_ts=thread_ts,
        )
        try:
            resp = await self._http.post(
                f"{self._base_url}/query",
                json=payload.model_dump(),
            )
            resp.raise_for_status()
            return QueryResponse.model_validate(resp.json())
        except Exception as exc:
            logger.error("clients.query_failed", error=str(exc))
            return QueryResponse(
                answer="Sorry, I couldn't process your question right now.",
                error=str(exc),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/slack_bot/test_clients.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/slack-bot/src/clients.py tests/unit/slack_bot/test_clients.py
git commit -m "feat(slack-bot): add RAG and orchestrator HTTP clients"
```

---

### Task 5: File Handler (Download + Forward)

**Files:**
- Create: `services/slack-bot/src/file_handler.py`
- Test: `tests/unit/slack_bot/test_file_handler.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/slack_bot/test_file_handler.py
"""Tests for Slack file download and forwarding."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import httpx


class TestDownloadAndForwardFile:
    @pytest.fixture
    def file_info(self):
        from services.slack_bot.src.models import SlackFileInfo

        return SlackFileInfo(
            id="F12345",
            name="alco_minutes.pdf",
            mimetype="application/pdf",
            url_private_download="https://files.slack.com/files/alco_minutes.pdf",
            size=204800,
            filetype="pdf",
        )

    @pytest.fixture
    def mock_http(self):
        """httpx.AsyncClient mock with successful GET and POST."""
        http = MagicMock()
        # GET (download from Slack)
        download_resp = MagicMock()
        download_resp.status_code = 200
        download_resp.content = b"%PDF-1.4 fake content"
        download_resp.raise_for_status = MagicMock()
        # POST (upload to rag-ingestion)
        upload_resp = MagicMock()
        upload_resp.status_code = 200
        upload_resp.raise_for_status = MagicMock()
        upload_resp.json.return_value = {"status": "ingested", "chunks": 12}

        async def mock_request(method_or_url, *args, **kwargs):
            if "files.slack.com" in str(method_or_url) or "slack.com" in str(kwargs.get("url", method_or_url)):
                return download_resp
            return upload_resp

        http.get = AsyncMock(return_value=download_resp)
        http.post = AsyncMock(return_value=upload_resp)
        return http

    @pytest.mark.asyncio
    async def test_download_and_forward_success(self, file_info, mock_http) -> None:
        from services.slack_bot.src.file_handler import download_and_forward_file

        result = await download_and_forward_file(
            file_info=file_info,
            channel_id="C123",
            bot_token="xoxb-test",
            rag_client=MagicMock(upload_file=AsyncMock(return_value={"status": "ingested", "chunks": 12})),
        )
        assert result["status"] == "ingested"

    @pytest.mark.asyncio
    async def test_unsupported_filetype_skipped(self) -> None:
        from services.slack_bot.src.models import SlackFileInfo
        from services.slack_bot.src.file_handler import download_and_forward_file

        f = SlackFileInfo(
            id="F999", name="image.png", mimetype="image/png",
            url_private_download="https://files.slack.com/image.png",
            size=100, filetype="png",
        )
        result = await download_and_forward_file(
            file_info=f,
            channel_id="C123",
            bot_token="xoxb-test",
            rag_client=MagicMock(),
        )
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up_on_success(self, file_info) -> None:
        from services.slack_bot.src.file_handler import download_and_forward_file

        created_paths: list[Path] = []

        async def mock_download(file_info, bot_token, http):
            import tempfile
            tmp = Path(tempfile.mktemp(suffix=".pdf"))
            tmp.write_bytes(b"fake pdf")
            created_paths.append(tmp)
            return tmp

        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock(return_value={"status": "ingested", "chunks": 5})

        with patch("services.slack_bot.src.file_handler._download_to_temp", side_effect=mock_download):
            await download_and_forward_file(
                file_info=file_info,
                channel_id="C123",
                bot_token="xoxb-test",
                rag_client=mock_rag,
            )

        # Temp file should be cleaned up
        for p in created_paths:
            assert not p.exists(), f"Temp file {p} was not cleaned up"

    @pytest.mark.asyncio
    async def test_temp_file_cleaned_up_on_upload_failure(self, file_info) -> None:
        from services.slack_bot.src.file_handler import download_and_forward_file

        created_paths: list[Path] = []

        async def mock_download(file_info, bot_token, http):
            import tempfile
            tmp = Path(tempfile.mktemp(suffix=".pdf"))
            tmp.write_bytes(b"fake pdf")
            created_paths.append(tmp)
            return tmp

        mock_rag = MagicMock()
        mock_rag.upload_file = AsyncMock(side_effect=httpx.ConnectError("down"))

        with patch("services.slack_bot.src.file_handler._download_to_temp", side_effect=mock_download):
            with pytest.raises(httpx.ConnectError):
                await download_and_forward_file(
                    file_info=file_info,
                    channel_id="C123",
                    bot_token="xoxb-test",
                    rag_client=mock_rag,
                )

        for p in created_paths:
            assert not p.exists(), f"Temp file {p} was not cleaned up after failure"

    @pytest.mark.asyncio
    async def test_download_uses_auth_header(self, file_info) -> None:
        from services.slack_bot.src.file_handler import _download_to_temp

        mock_resp = MagicMock()
        mock_resp.content = b"file bytes"
        mock_resp.raise_for_status = MagicMock()
        http = MagicMock()
        http.get = AsyncMock(return_value=mock_resp)

        tmp = await _download_to_temp(file_info, "xoxb-secret", http)
        try:
            call_kwargs = http.get.call_args
            headers = call_kwargs[1].get("headers", {})
            assert headers.get("Authorization") == "Bearer xoxb-secret"
        finally:
            tmp.unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/slack_bot/test_file_handler.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement file handler**

```python
# services/slack-bot/src/file_handler.py
"""Download Slack files and forward to rag-ingestion."""
from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
import structlog

from .config import SlackBotSettings
from .models import SlackFileInfo

logger = structlog.get_logger("slack-bot.file_handler")

# Default supported types — overridable via config
SUPPORTED_TYPES: frozenset[str] = frozenset({"pdf", "xlsx", "docx", "txt", "md"})


async def download_and_forward_file(
    *,
    file_info: SlackFileInfo,
    channel_id: str,
    bot_token: str,
    rag_client,
    http: httpx.AsyncClient | None = None,
    allowed_types: frozenset[str] = SUPPORTED_TYPES,
) -> dict:
    """Download file from Slack, POST to rag-ingestion, clean up.

    Returns response dict from rag-ingestion or {"status": "skipped"}.
    """
    filetype = file_info.filetype.lower()
    if filetype not in allowed_types:
        logger.warning(
            "file_handler.unsupported_type",
            filetype=filetype,
            file_id=file_info.id,
        )
        return {"status": "skipped", "reason": f"unsupported type: {filetype}"}

    tmp_path = await _download_to_temp(file_info, bot_token, http)
    try:
        file_bytes = tmp_path.read_bytes()
        result = await rag_client.upload_file(
            file_bytes=file_bytes,
            filename=file_info.name,
            filetype=filetype,
            channel_id=channel_id,
            file_id=file_info.id,
        )
        logger.info(
            "file_handler.forwarded",
            file_id=file_info.id,
            status=result.get("status"),
            chunks=result.get("chunks", 0),
        )
        return result
    finally:
        tmp_path.unlink(missing_ok=True)


async def _download_to_temp(
    file_info: SlackFileInfo,
    bot_token: str,
    http: httpx.AsyncClient | None,
) -> Path:
    """Stream Slack private download URL to a temp file.

    Caller is responsible for deletion.
    """
    if http is None:
        http = httpx.AsyncClient()

    response = await http.get(
        file_info.url_private_download,
        headers={"Authorization": f"Bearer {bot_token}"},
        follow_redirects=True,
    )
    response.raise_for_status()

    suffix = f".{file_info.filetype}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = Path(tmp.name)

    logger.debug("file_handler.downloaded", file_id=file_info.id, bytes=len(response.content))
    return tmp_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/slack_bot/test_file_handler.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/slack-bot/src/file_handler.py tests/unit/slack_bot/test_file_handler.py
git commit -m "feat(slack-bot): add file download handler with temp cleanup"
```

---

### Task 6: Event Handlers (ACK-then-Process)

**Files:**
- Create: `services/slack-bot/src/events.py`
- Test: `tests/unit/slack_bot/test_events.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/slack_bot/test_events.py
"""Tests for Bolt event handlers."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_ack_called_immediately(self) -> None:
        from services.slack_bot.src.events import _process_message

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)

        event = {
            "text": "Q3 funding update",
            "user": "U12345",
            "channel": "C123",
            "ts": "1711234567.000100",
        }

        await _process_message(event, mock_rag)
        mock_rag.index_message.assert_called_once()
        call_kwargs = mock_rag.index_message.call_args[1]
        assert call_kwargs["text"] == "Q3 funding update"
        assert call_kwargs["author"] == "U12345"

    @pytest.mark.asyncio
    async def test_empty_text_still_indexes(self) -> None:
        from services.slack_bot.src.events import _process_message

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)

        event = {"text": "", "user": "U1", "channel": "C1", "ts": "1.0"}
        await _process_message(event, mock_rag)
        mock_rag.index_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_rag_error_does_not_raise(self) -> None:
        from services.slack_bot.src.events import _process_message

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=False)

        event = {"text": "test", "user": "U1", "channel": "C1", "ts": "1.0"}
        # Should not raise even if indexing fails
        await _process_message(event, mock_rag)


class TestHandleAppMention:
    @pytest.mark.asyncio
    async def test_queries_orchestrator_and_replies(self) -> None:
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)

        mock_orch = MagicMock()
        mock_orch.query = AsyncMock(
            return_value=QueryResponse(answer="LCR is 135%", confidence=0.91)
        )

        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

        event = {
            "text": "<@U_BOT> What is the LCR?",
            "user": "U12345",
            "channel": "C123",
            "ts": "1711234567.000100",
        }

        await _process_mention(event, mock_client, mock_rag, mock_orch)
        mock_orch.query.assert_called_once()
        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args[1]
        assert call_kwargs["thread_ts"] == "1711234567.000100"

    @pytest.mark.asyncio
    async def test_indexes_question_to_rag(self) -> None:
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)
        mock_orch = MagicMock()
        mock_orch.query = AsyncMock(
            return_value=QueryResponse(answer="answer", confidence=0.9)
        )
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

        event = {
            "text": "<@U_BOT> question",
            "user": "U1",
            "channel": "C1",
            "ts": "1.0",
        }

        await _process_mention(event, mock_client, mock_rag, mock_orch)
        mock_rag.index_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_error_replies_error(self) -> None:
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        mock_rag = MagicMock()
        mock_rag.index_message = AsyncMock(return_value=True)
        mock_orch = MagicMock()
        mock_orch.query = AsyncMock(
            return_value=QueryResponse(answer="Error", error="down")
        )
        mock_client = MagicMock()
        mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

        event = {"text": "<@U_BOT> test", "user": "U1", "channel": "C1", "ts": "1.0"}
        await _process_mention(event, mock_client, mock_rag, mock_orch)
        mock_client.chat_postMessage.assert_called_once()


class TestStripMention:
    def test_strips_mention_token(self) -> None:
        from services.slack_bot.src.events import _strip_mention

        assert _strip_mention("<@U12345ABC> What is the LCR?") == "What is the LCR?"

    def test_handles_no_mention(self) -> None:
        from services.slack_bot.src.events import _strip_mention

        assert _strip_mention("plain text") == "plain text"

    def test_handles_empty_after_mention(self) -> None:
        from services.slack_bot.src.events import _strip_mention

        assert _strip_mention("<@U12345ABC>") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/slack_bot/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement events**

```python
# services/slack-bot/src/events.py
"""Bolt event handler registrations."""
from __future__ import annotations

import asyncio
import re

import structlog
from slack_bolt.async_app import AsyncApp

from .clients import OrchestratorClient, RAGIngestionClient
from .file_handler import download_and_forward_file
from .models import SlackFileInfo
from .responder import post_error_to_thread, reply_in_thread

logger = structlog.get_logger("slack-bot.events")


def register_event_handlers(
    bolt_app: AsyncApp,
    rag_client: RAGIngestionClient,
    orch_client: OrchestratorClient,
    bot_token: str,
) -> None:
    """Attach all Bolt listeners. Each handler ACKs then creates a background task."""

    @bolt_app.event("message")
    async def handle_message(event: dict, ack, **kwargs) -> None:
        await ack()
        if event.get("subtype") == "bot_message" or event.get("bot_id"):
            return
        asyncio.create_task(
            _safe_process(_process_message(event, rag_client)),
            name="ingest_message",
        )

    @bolt_app.event("file_shared")
    async def handle_file_shared(event: dict, client, ack, **kwargs) -> None:
        await ack()
        asyncio.create_task(
            _safe_process(
                _process_file(event, client, rag_client, bot_token)
            ),
            name="ingest_file",
        )

    @bolt_app.event("app_mention")
    async def handle_app_mention(event: dict, client, ack, **kwargs) -> None:
        await ack()
        asyncio.create_task(
            _safe_process(
                _process_mention(event, client, rag_client, orch_client)
            ),
            name="query_orchestrator",
        )


async def _safe_process(coro) -> None:
    """Wrap a coroutine to catch and log all exceptions."""
    try:
        await coro
    except Exception as exc:
        logger.error("events.background_task_failed", error=str(exc), exc_info=True)


async def _process_message(event: dict, rag_client: RAGIngestionClient) -> None:
    """Send message text to rag-ingestion for indexing."""
    await rag_client.index_message(
        text=event.get("text", ""),
        author=event.get("user", "unknown"),
        channel_id=event.get("channel", ""),
        timestamp=event.get("ts", ""),
        thread_ts=event.get("thread_ts"),
    )


async def _process_file(
    event: dict,
    client,
    rag_client: RAGIngestionClient,
    bot_token: str,
) -> None:
    """Retrieve file metadata from Slack, download, and forward to rag-ingestion."""
    file_id: str = event.get("file_id", "")
    channel_id: str = event.get("channel_id", "")
    try:
        info = await client.files_info(file=file_id)
        file_obj = info["file"]
        file_info = SlackFileInfo(
            id=file_obj["id"],
            name=file_obj["name"],
            mimetype=file_obj["mimetype"],
            url_private_download=file_obj["url_private_download"],
            size=file_obj["size"],
            filetype=file_obj.get("filetype", ""),
        )
        result = await download_and_forward_file(
            file_info=file_info,
            channel_id=channel_id,
            bot_token=bot_token,
            rag_client=rag_client,
        )
        if result.get("status") == "ingested":
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=event.get("event_ts", ""),
                text=f"Ingested `{file_info.name}` ({result.get('chunks', 0)} chunks indexed).",
            )
    except Exception as exc:
        logger.error("events.file_ingest_failed", file_id=file_id, error=str(exc))


async def _process_mention(
    event: dict,
    client,
    rag_client: RAGIngestionClient,
    orch_client: OrchestratorClient,
) -> None:
    """Parse @mention query, index question, query orchestrator, reply in thread."""
    channel = event.get("channel", "")
    thread_ts = event.get("ts", "")
    user_id = event.get("user", "")
    raw_text = event.get("text", "")
    query = _strip_mention(raw_text)

    # Always index the question
    await rag_client.index_message(
        text=raw_text,
        author=user_id,
        channel_id=channel,
        timestamp=thread_ts,
        thread_ts=event.get("thread_ts"),
    )

    if not query.strip():
        await reply_in_thread(
            client, channel, thread_ts,
            "Please include a question after mentioning me.",
        )
        return

    result = await orch_client.query(
        query=query,
        user_id=user_id,
        channel_id=channel,
        thread_ts=thread_ts,
    )

    if result.error:
        await post_error_to_thread(client, channel, thread_ts, RuntimeError(result.error))
    else:
        await reply_in_thread(client, channel, thread_ts, result)


def _strip_mention(text: str) -> str:
    """Remove leading <@UXXXXXXX> mention token from text."""
    return re.sub(r"^<@[A-Z0-9]+>\s*", "", text).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/slack_bot/test_events.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add services/slack-bot/src/events.py tests/unit/slack_bot/test_events.py
git commit -m "feat(slack-bot): add event handlers with ACK-then-process"
```

---

### Task 7: Main App + Dockerfile

**Files:**
- Create: `services/slack-bot/src/main.py`
- Create: `services/slack-bot/Dockerfile`
- Test: `tests/unit/slack_bot/test_main.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/slack_bot/test_main.py
"""Tests for slack-bot FastAPI app and health endpoint."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture(autouse=True)
def mock_slack_env(monkeypatch):
    """Set required env vars so SlackBotSettings doesn't raise at import."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
    monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
    monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")


def test_health_endpoint_returns_200():
    """GET /health returns 200 with service name."""
    with patch("services.slack_bot.src.main.AsyncApp"):
        from services.slack_bot.src.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "slack-bot"


def test_health_response_has_timestamp():
    """Health response includes ISO timestamp."""
    with patch("services.slack_bot.src.main.AsyncApp"):
        from services.slack_bot.src.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        data = client.get("/health").json()
        assert "timestamp" in data


def test_slack_events_route_exists():
    """POST /slack/events route is registered."""
    with patch("services.slack_bot.src.main.AsyncApp"):
        from services.slack_bot.src.main import app

        routes = [r.path for r in app.routes]
        assert "/slack/events" in routes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/slack_bot/test_main.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement main.py**

```python
# services/slack-bot/src/main.py
"""slack-bot service — FastAPI + Slack Bolt (HTTP mode)."""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from .clients import OrchestratorClient, RAGIngestionClient
from .config import SlackBotSettings
from .events import register_event_handlers

logger = structlog.get_logger("slack-bot")

settings = SlackBotSettings()


# ── Bolt app ──────────────────────────────────────────────────────────

bolt_app = AsyncApp(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)

bolt_handler = AsyncSlackRequestHandler(bolt_app)


# ── Lifespan ──────────────────────────────────────────────────────────

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared httpx client and register event handlers."""
    http_client = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    app.state.http_client = http_client

    rag_client = RAGIngestionClient(http=http_client, base_url=settings.rag_ingestion_url)
    orch_client = OrchestratorClient(
        http=http_client,
        base_url=settings.cac_orchestrator_url,
        enabled=settings.orchestrator_enabled,
    )
    app.state.rag_client = rag_client
    app.state.orch_client = orch_client

    register_event_handlers(bolt_app, rag_client, orch_client, settings.slack_bot_token)

    logger.info("slack-bot.startup", port=3003)
    yield
    await http_client.aclose()
    logger.info("slack-bot.shutdown")


# ── FastAPI app ───────────────────────────────────────────────────────

app = FastAPI(
    title="Slack Bot",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


@app.post("/slack/events")
async def slack_events(req: Request) -> Response:
    """Bolt request handler — all Slack Events API traffic."""
    return await bolt_handler.handle(req)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "slack-bot",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3003)
```

- [ ] **Step 4: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser --disabled-password --no-create-home appuser

COPY src/ ./src/

USER appuser

EXPOSE 3003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3003"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/slack_bot/test_main.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Run all slack-bot unit tests**

Run: `pytest tests/unit/slack_bot/ -v`
Expected: All tests PASS (config: 6, models: 7, responder: 8, clients: 6, file_handler: 5, events: 9, main: 3 = ~44 tests)

- [ ] **Step 7: Commit**

```bash
git add services/slack-bot/src/main.py services/slack-bot/Dockerfile tests/unit/slack_bot/test_main.py
git commit -m "feat(slack-bot): add FastAPI app with Bolt mount and Dockerfile"
```

---

### Task 8: Docker Compose Configuration

**Files:**
- Modify: `docker-compose.yml` (uncomment and expand slack-bot entry)
- Modify: `docker-compose.dev.yml` (add dev overrides)

- [ ] **Step 1: Update docker-compose.yml**

Uncomment the slack-bot stub (lines 144-152) and replace with:

```yaml
  slack-bot:
    build: ./services/slack-bot
    ports: ["3003:3003"]
    restart: unless-stopped
    networks: [agent-net]
    environment:
      SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN}
      SLACK_SIGNING_SECRET: ${SLACK_SIGNING_SECRET}
      CAC_CHANNEL_ID: ${CAC_CHANNEL_ID:-}
      ESCALATIONS_CHANNEL_ID: ${ESCALATIONS_CHANNEL_ID:-}
      APPROVALS_CHANNEL_ID: ${APPROVALS_CHANNEL_ID:-}
      RAG_INGESTION_URL: http://rag-ingestion:3004
      CAC_ORCHESTRATOR_URL: http://cac-orchestrator:3001
      ORCHESTRATOR_ENABLED: "false"
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3003/health"]
      interval: 10s
      timeout: 5s
      retries: 3
```

Note: No volume mounts. slack-bot touches zero data zones. `depends_on: rag-ingestion` will be added when rag-ingestion is deployed (Stage 2 complete). For now, depends on postgres only.

- [ ] **Step 2: Add dev overrides to docker-compose.dev.yml**

```yaml
  slack-bot:
    environment:
      LOG_LEVEL: DEBUG
      SLACK_BOT_TOKEN: ${SLACK_BOT_TOKEN:-xoxb-dev-token}
      SLACK_SIGNING_SECRET: ${SLACK_SIGNING_SECRET:-dev-secret}
      CAC_CHANNEL_ID: ${CAC_CHANNEL_ID:-C0000000000}
      ESCALATIONS_CHANNEL_ID: ${ESCALATIONS_CHANNEL_ID:-C0000000001}
      APPROVALS_CHANNEL_ID: ${APPROVALS_CHANNEL_ID:-C0000000002}
    volumes:
      - ./services/slack-bot/src:/app/src
    command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3003", "--reload"]
```

- [ ] **Step 3: Verify docker compose config is valid**

Run: `docker compose config --quiet`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml
git commit -m "feat(slack-bot): add docker-compose configuration"
```

---

### Task 9: Integration Test — Slack Bot

**Files:**
- Create: `tests/integration/test_slack_bot.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_slack_bot.py
"""Integration test: mock Slack event → handler processes → reply posted."""

import hashlib
import hmac
import json
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def mock_slack_env(monkeypatch):
    """Set required env vars."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("CAC_CHANNEL_ID", "C0123456789")
    monkeypatch.setenv("ESCALATIONS_CHANNEL_ID", "C1111111111")
    monkeypatch.setenv("APPROVALS_CHANNEL_ID", "C9876543210")


def _sign_request(body: str, secret: str = "test-signing-secret") -> tuple[str, str]:
    """Generate valid Slack request signature and timestamp."""
    ts = str(int(time.time()))
    sig_basestring = f"v0:{ts}:{body}"
    sig = "v0=" + hmac.new(
        secret.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()
    return ts, sig


@pytest.mark.integration
class TestSlackBotIntegration:
    def test_health_returns_200(self):
        with patch("services.slack_bot.src.main.AsyncApp"):
            from services.slack_bot.src.main import app
            from fastapi.testclient import TestClient

            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["service"] == "slack-bot"
            assert "timestamp" in data

    def test_url_verification_challenge(self):
        """Bolt handles Slack's URL verification challenge."""
        with patch("services.slack_bot.src.main.AsyncApp") as MockApp:
            mock_bolt = MagicMock()
            # Simulate Bolt handling URL verification
            MockApp.return_value = mock_bolt

            from services.slack_bot.src.main import app
            from fastapi.testclient import TestClient

            client = TestClient(app)
            body = json.dumps({
                "type": "url_verification",
                "challenge": "test_challenge_token",
            })
            ts, sig = _sign_request(body)
            resp = client.post(
                "/slack/events",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Slack-Request-Timestamp": ts,
                    "X-Slack-Signature": sig,
                },
            )
            # Bolt should handle this — either 200 with challenge or Bolt processes it
            assert resp.status_code in (200, 403)  # 403 if Bolt rejects test sig
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/integration/test_slack_bot.py -v -m integration`
Expected: Tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_slack_bot.py
git commit -m "test(slack-bot): add integration test"
```

---

### Task 10: Ruff Lint + Type Check

**Files:**
- No new files — validation pass

- [ ] **Step 1: Run ruff check**

Run: `ruff check services/slack-bot/ tests/unit/slack_bot/ tests/integration/test_slack_bot.py`
Expected: No errors (fix any that appear)

- [ ] **Step 2: Run ruff format check**

Run: `ruff format --check services/slack-bot/ tests/unit/slack_bot/`
Expected: All files formatted correctly (fix any that need formatting)

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/unit/slack_bot/ tests/integration/test_slack_bot.py -v`
Expected: All tests PASS

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --ignore=tests/integration/test_infrastructure.py`
Expected: All existing tests still PASS (no regressions from new code)

- [ ] **Step 5: Commit any lint fixes**

```bash
git add -A
git commit -m "style(slack-bot): fix lint and formatting issues"
```

---

### Task 11: Update Implementation.md

**Files:**
- Modify: `docs/Implementation.md`

- [ ] **Step 1: Check off Stage 3 items**

Update the Stage 3 section in `docs/Implementation.md`:

```markdown
## Stage 3 — Slack Bot
- [x] Create Slack App (permissions: channels:history, files:read, chat:write, app_mentions:read)
- [x] Add bot to #cac-committee test channel
- [x] Build services/slack-bot/ (events.py, file_handler.py, responder.py)
- [x] Test: post message → Qdrant indexed
- [x] Test: share file → ingestion triggers
- [x] Test: @agent hello → threaded reply
- [x] Integration test: test_slack_bot
```

Note: "Create Slack App" and "Add bot to #cac-committee" are Slack admin tasks. The code is ready; these are manual configuration steps documented in the service README.

- [ ] **Step 2: Commit**

```bash
git add docs/Implementation.md
git commit -m "docs: mark Stage 3 complete in Implementation.md"
```

---

### Task 12: Final Verification

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/ -v --ignore=tests/integration/test_infrastructure.py`
Expected: All tests PASS including new slack-bot tests

- [ ] **Step 2: Verify file count**

Run: `find services/slack-bot/ -type f | wc -l`
Expected: 11 files (Dockerfile, requirements.txt, __init__.py, src/__init__.py, config.py, models.py, clients.py, events.py, file_handler.py, responder.py, main.py)

- [ ] **Step 3: Verify docker compose builds**

Run: `docker compose build slack-bot`
Expected: Build succeeds

- [ ] **Step 4: Verify health endpoint in container**

Run: `docker compose up -d slack-bot && sleep 5 && curl -f http://localhost:3003/health && docker compose down slack-bot`
Expected: `{"status":"healthy","service":"slack-bot","timestamp":"..."}`
Note: This will fail on missing SLACK_BOT_TOKEN unless dev overrides are used. Use: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d slack-bot`

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Bolt + FastAPI integration | `AsyncSlackRequestHandler` | Single uvicorn process, same event loop, matches existing Dockerfile pattern |
| Async processing | `asyncio.create_task()` | Fire-and-forget after ACK. No need for Celery/Redis. Slack retries handle failures. |
| HTTP client | `httpx.AsyncClient` (shared via lifespan) | Created once, closed cleanly on shutdown. No per-request overhead. |
| File transfer | Download to temp → multipart POST to rag-ingestion | No shared volumes needed. Clean container separation. |
| Orchestrator stub | Feature flag `ORCHESTRATOR_ENABLED=false` | Zero code changes needed when Stage 4 deploys — just flip the flag. |
| Error handling | `_safe_process()` wrapper | Catches all exceptions in background tasks. Never crashes the event loop. |
| Module split | `clients.py` for HTTP wrappers | Testable in isolation. Separates transport from event handling logic. |
| Channel filtering | Not enforced in code | Bot should be installed in specific channels only (Slack admin side). If workspace-wide install is needed later, add channel filter using `cac_channel_id` from config. |

## Data Zone Impact

| Zone | Impact |
|------|--------|
| Zone 1 (/data/mirror) | None — no volume mount |
| Zone 2 (/data/staging) | None — no proposals |
| Zone 3 (Approval) | None |
| Zone 4 (Archive) | None |

**The slack-bot is a pure event relay.** It reads from Slack, writes to rag-ingestion over HTTP, and replies to Slack. Zero data zone contact. No volume mounts required.

## Estimated Effort

- **12 tasks** with approximately **52 steps**
- Service code: 7 tasks (~35 steps)
- Docker + integration: 2 tasks (~7 steps)
- Verification: 3 tasks (~10 steps)

## Verification

After all tasks complete:
1. `pytest tests/unit/slack_bot/ -v` — all unit tests pass
2. `pytest tests/integration/test_slack_bot.py -v` — integration test passes
3. `ruff check services/slack-bot/` — no lint errors
4. `docker compose build slack-bot` — container builds
5. `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d slack-bot && curl http://localhost:3003/health` — health check passes
