"""HTTP client wrappers for downstream services."""
from __future__ import annotations

import re

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .intent_router import IntentRouter, make_default_router
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
    """Multi-dept dispatcher.

    Picks an orchestrator URL based on a `[dept]` prefix in the message, falling
    back to cac. Read-only depts share the read-only-orchestrator container which
    needs `dept_id` in the request body to dispatch correctly.
    """

    STUB_MESSAGE = (
        "I'm still being set up and can't answer questions yet. "
        "Your message has been noted and indexed."
    )

    # Static map: dept_id -> (orchestrator URL, response shape).
    # read-only depts all live behind read-only-orchestrator:3040 and use the
    # `pipeline.py` response shape ({response, citations, ...}).
    # cac/hr have their own orchestrators with the QueryResponse shape
    # ({answer, sources, confidence, ...}).
    _RO_URL = "http://read-only-orchestrator:3040"
    _DEPT_ROUTES: dict[str, tuple[str, str]] = {
        "cac":     ("http://cac-orchestrator:3001", "cac"),
        "hr":      ("http://hr-orchestrator:3002",  "cac"),  # hr-orch returns CAC shape
        "risk":    (_RO_URL, "read_only"),
        "legal":   (_RO_URL, "read_only"),
        "it":      (_RO_URL, "read_only"),
        "comms":   (_RO_URL, "read_only"),
        "ic":      (_RO_URL, "read_only"),
        "ib":      (_RO_URL, "read_only"),
        "ceo":     (_RO_URL, "read_only"),
        # write-capable depts whose real orchestrators don't exist yet —
        # serve read queries via read-only-orchestrator for now.
        "finance": (_RO_URL, "read_only"),
        "cio":     (_RO_URL, "read_only"),
        "vcc":     (_RO_URL, "read_only"),
        # Artefact-producing services use the cac response shape but also set
        # file_path/file_url which the responder will upload to the thread.
        "deck":    ("http://deck-writer:3050", "cac"),
        # report-writer uses the same shape but emits .docx via /report.
        "report":  ("http://deck-writer:3050/report", "cac_path"),
        # Specialised cac endpoints (alternate routes within the same orchestrator)
        "summary": ("http://cac-orchestrator:3001/summary", "cac_path"),
        # proposals listing has a different shape (count + proposals list)
        "proposals": ("http://cac-orchestrator:3001/proposals/pending", "proposals_list"),
    }

    _PREFIX_RE = re.compile(r"^\s*\[([a-z]+)\]\s*", re.IGNORECASE)

    def __init__(
        self,
        http: httpx.AsyncClient,
        base_url: str,
        enabled: bool = False,
        intent_router: IntentRouter | None = None,
    ) -> None:
        self._http = http
        self._default_dept = "cac"  # fallback when no [dept] prefix
        self._enabled = enabled
        # Lazy build a router if one wasn't injected. Single instance per process.
        self._intent_router = intent_router or make_default_router()

    def _parse_dept(self, query: str) -> tuple[str, str, bool]:
        """Extract `[dept]` prefix.

        Returns (dept_id, stripped_query, was_explicit).
        was_explicit=True when the user typed a [...] prefix we recognised.
        """
        m = self._PREFIX_RE.match(query)
        if m and m.group(1).lower() in self._DEPT_ROUTES:
            return (
                m.group(1).lower(),
                self._PREFIX_RE.sub("", query, count=1).strip(),
                True,
            )
        return self._default_dept, query, False

    async def query(
        self,
        *,
        query: str,
        user_id: str,
        channel: str,
        thread_ts: str | None = None,
        channel_dept: str | None = None,
    ) -> QueryResponse:
        """Dispatch query to the right orchestrator.

        Routing order:
          1. Explicit `[dept]` prefix wins (no LLM call).
          2. Otherwise, the LLM intent classifier picks `deck` vs `chat`.
          3. `chat` routes to the channel's department (channel_dept) when the
             message came from a dept committee channel (e.g. #risk-committee).
          4. Otherwise falls through to the default dept (cac).
        """
        if not self._enabled:
            return QueryResponse(answer=self.STUB_MESSAGE)

        dept_id, stripped_query, explicit = self._parse_dept(query)
        if not explicit:
            intent = await self._intent_router.classify(stripped_query)
            if intent.name == "deck":
                dept_id = "deck"
            elif channel_dept and channel_dept in self._DEPT_ROUTES:
                dept_id = channel_dept
        url, shape = self._DEPT_ROUTES[dept_id]

        # `proposals` has no body — it's a GET listing endpoint.
        if shape == "proposals_list":
            try:
                logger.info("clients.query_dispatch", dept_id=dept_id, url=url)
                resp = await self._http.get(url)
                resp.raise_for_status()
                body = resp.json()
                return _format_proposals_response(body)
            except Exception as exc:
                logger.error("clients.query_failed", dept_id=dept_id, error=str(exc))
                return QueryResponse(answer="Couldn't read pending proposals.",
                                     error=str(exc))

        payload_obj = QueryRequest(
            query=stripped_query,
            channel=channel,
            user_id=user_id,
            thread_ts=thread_ts,
            dept_id=dept_id,
        )
        # `cac_path` routes (summary/report) take the full URL incl. path — don't
        # append /query. Everything else POSTs to {base}/query.
        post_url = url if shape == "cac_path" else f"{url.rstrip('/')}/query"
        try:
            logger.info("clients.query_dispatch", dept_id=dept_id, url=post_url)
            resp = await self._http.post(post_url, json=payload_obj.model_dump())
            resp.raise_for_status()
            body = resp.json()
            if shape == "read_only":
                # pipeline.py returns {response, citations, dept_id, chunks_retrieved, latency_ms}
                return QueryResponse(
                    answer=body.get("response", ""),
                    confidence="Low",
                )
            return QueryResponse.model_validate(body)
        except Exception as exc:
            logger.error("clients.query_failed", dept_id=dept_id, error=str(exc))
            return QueryResponse(
                answer="Sorry, I couldn't process your question right now.",
                error=str(exc),
            )


def _format_proposals_response(body: dict) -> QueryResponse:
    """Render the proposals-listing JSON into a Slack-friendly text answer."""
    items = body.get("proposals", []) or []
    if not items:
        return QueryResponse(
            answer=":inbox_tray: No pending staging proposals.",
            confidence="High",
        )
    lines = [f":inbox_tray: *{len(items)} pending staging proposal" + ("s" if len(items) != 1 else "") + "*"]
    for p in items[:25]:
        cell = f"{p.get('tab','?')}!{p.get('cell','?')}"
        delta = f"{p.get('old_value','—')} → *{p.get('new_value','?')}*"
        conf = p.get("confidence")
        conf_s = f"  conf={conf:.0%}" if isinstance(conf, (int, float)) else ""
        lines.append(
            f"\n• `{p.get('id','?')}` · {cell} · {delta}{conf_s}\n"
            f"   _agent_: {p.get('agent','?')}\n"
            f"   _why_: {(p.get('reasoning','') or '')[:120]}"
        )
    return QueryResponse(answer="\n".join(lines), confidence="High")
