"""HTTP client wrappers for downstream services."""
from __future__ import annotations

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models import IngestMessageRequest, QueryRequest, QueryResponse

logger = structlog.get_logger("slack-bot.clients")

# Retry decorator for transient network errors
_retry_on_transport = retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


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

    @_retry_on_transport
    async def upload_file(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        filetype: str,
        channel_id: str,
        file_id: str,
    ) -> dict:  # type: ignore[type-arg]
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
        return resp.json()  # type: ignore[no-any-return]

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
        channel: str,
        thread_ts: str | None = None,
    ) -> QueryResponse:
        """Send query to cac-orchestrator. Returns stub when disabled."""
        if not self._enabled:
            return QueryResponse(answer=self.STUB_MESSAGE, confidence=0.0)

        payload = QueryRequest(
            query=query,
            channel=channel,
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
