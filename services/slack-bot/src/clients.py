"""HTTP client wrappers for downstream services."""
from __future__ import annotations

import re
from typing import Any

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
        # CAC meeting report first draft — GET, reads the live Excel Online data
        # pack and returns a DETERMINISTIC .docx (file_url) the bot uploads to the
        # thread. deck-writer (not the orchestrator) owns this: it has python-docx
        # + the /reports file route, and builds the doc with no LLM rewriting.
        "cac-report": ("http://deck-writer:3050/report/cac-meeting", "report_docx"),
    }

    _PREFIX_RE = re.compile(r"^\s*\[([a-z]+)\]\s*", re.IGNORECASE)

    # Slack renders links as <url> or <url|label>; this stops at the delimiters.
    _URL_RE = re.compile(r"https?://[^\s|<>]+")
    _XLSX_HOSTS = ("sharepoint.com", "1drv.ms", "onedrive")

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

    @classmethod
    def _extract_xlsx_url(cls, text: str) -> str | None:
        """Pull the first SharePoint/OneDrive link out of (Slack-formatted) text."""
        for m in cls._URL_RE.finditer(text):
            u = m.group(0)
            if any(h in u.lower() for h in cls._XLSX_HOSTS):
                return u
        return None

    @classmethod
    def _wants_cac_report(cls, text: str, channel_dept: str | None) -> bool:
        """True when the message asks for a CAC report and carries an Excel link.

        STRICT ISOLATION: the CAC monthly report is a CAC-owned artefact. Even though
        the .docx is addressed "To: Supane, CFO", it is sourced from the CAC Data Pack
        and managed by the CAC committee — finance/cfo channels do NOT trigger it
        here. (deck-writer's /report/cac-meeting also enforces caller_dept as a second
        layer.) Text words like "cac"/"meeting"/"data pack" still trigger, so users
        outside #cac-committee can ask for the CAC report by name and the dept guard
        will tell them to use the right channel.
        """
        if cls._extract_xlsx_url(text) is None:
            return False
        t = text.lower()
        if "report" not in t and "draft" not in t:
            return False
        return (
            "cac" in t
            or "meeting" in t
            or "data pack" in t
            or channel_dept == "cac"
        )

    async def query(
        self,
        *,
        query: str,
        user_id: str,
        channel: str,
        thread_ts: str | None = None,
        channel_dept: str | None = None,
        images: list[dict[str, Any]] | None = None,
    ) -> QueryResponse:
        """Dispatch query to the right orchestrator.

        Routing order:
          1. Explicit `[dept]` prefix wins (no LLM call).
          2. Otherwise, the LLM intent classifier picks `deck` vs `chat`.
          3. `chat` routes to the channel's department (channel_dept) when the
             message came from a dept committee channel (e.g. #risk-committee).
          4. Otherwise falls through to the default dept (cac).

        Parameters
        ----------
        images
            Optional list of ImagePlacementSpec dicts (from image_intent.py).
            Forwarded to deck-writer /compose and /report when non-empty.
            Ignored silently for all other routes (no schema change to those
            orchestrators).  Passing None or [] is equivalent — both result in
            no images field being sent.
        """
        if not self._enabled:
            return QueryResponse(answer=self.STUB_MESSAGE)

        dept_id, stripped_query, explicit = self._parse_dept(query)
        if not explicit:
            # Deterministic: an Excel Online link + "report"/"draft" in a CAC
            # context is a CAC meeting report request — route there directly so
            # it never hits the slow RAG /query path or the LLM intent classifier.
            if self._wants_cac_report(stripped_query, channel_dept):
                dept_id = "cac-report"
            else:
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

        # `report_docx` (deck-writer /report/cac-meeting): builds the report .docx
        # deterministically and returns {answer, file_url, file_name, breaches}.
        # Setting file_url/file_name on the QueryResponse makes the responder upload
        # the Word document into the thread instead of posting markdown text.
        if shape == "report_docx":
            params = {}
            link = self._extract_xlsx_url(stripped_query)
            if link:
                params["share_url"] = link
            # caller_dept tells the endpoint who is asking, so it can enforce
            # dept boundaries (CAC report only from CAC context). 'unknown' is a
            # sentinel for Slack messages whose channel-dept couldn't be resolved
            # — the endpoint rejects it, surfacing a clear "wrong channel" error
            # instead of silently leaking. Direct curl (no Slack) omits the param.
            params["caller_dept"] = channel_dept or "unknown"
            try:
                logger.info("clients.query_dispatch", dept_id=dept_id, url=url,
                            caller_dept=params["caller_dept"], has_link=bool(link))
                resp = await self._http.get(url, params=params, timeout=180.0)
                resp.raise_for_status()
                body = resp.json()
                return QueryResponse(
                    answer=body.get("answer") or "CAC meeting report ready.",
                    confidence=body.get("confidence", "High"),
                    file_url=body.get("file_url"),
                    file_name=body.get("file_name"),
                    file_path=body.get("file_path"),
                )
            except httpx.HTTPStatusError as exc:
                # Surface 403 (dept guard) as a friendly chat reply, not the
                # generic "Sorry, I ran into an error" — the user needs to know
                # to post in #cac-committee.
                detail = ""
                try:
                    detail = exc.response.json().get("detail", "") or ""
                except Exception:
                    detail = (exc.response.text or "")[:200]
                status = exc.response.status_code
                logger.warning("clients.report_http_error", dept_id=dept_id,
                               status=status, detail=detail[:200])
                if status == 403:
                    return QueryResponse(
                        answer=f":lock: {detail or 'CAC report can only be requested from #cac-committee.'}",
                        confidence="High",
                    )
                return QueryResponse(answer="Couldn't generate the CAC meeting report.",
                                     error=f"HTTP {status}: {detail[:200]}")
            except Exception as exc:
                logger.error("clients.query_failed", dept_id=dept_id, error=str(exc))
                return QueryResponse(answer="Couldn't generate the CAC meeting report.",
                                     error=str(exc))

        # `cac-report` is a GET that returns {report: <markdown>, breaches: [...]}.
        # The user may paste an Excel Online share link after the command
        # (`[cac-report] https://...`); forward it as the share_url query param.
        if shape == "report_get":
            params = {}
            link = self._extract_xlsx_url(stripped_query)
            if link:
                params["share_url"] = link
            try:
                logger.info("clients.query_dispatch", dept_id=dept_id, url=url,
                            has_link=bool(params))
                resp = await self._http.get(url, params=params or None, timeout=120.0)
                resp.raise_for_status()
                body = resp.json()
                answer = body.get("report") or "No report generated."
                n = len(body.get("breaches", []) or [])
                if n:
                    answer += f"\n\n_{n} limit breach(es) flagged — see Executive Summary._"
                return QueryResponse(answer=answer, confidence="High")
            except Exception as exc:
                logger.error("clients.query_failed", dept_id=dept_id, error=str(exc))
                return QueryResponse(answer="Couldn't generate the CAC meeting report.",
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

        # Build the JSON payload. For deck-writer routes (dept_id in {"deck",
        # "report"} or shape == "cac_path" targeting deck-writer), merge the
        # images list into the body so deck-writer's ComposeRequest can embed
        # them.  For all other orchestrators we omit the field entirely to
        # avoid unexpected schema validation errors on their side.
        payload_dict = payload_obj.model_dump()
        _image_list = images or []
        if _image_list and dept_id in ("deck", "report") or (
            _image_list and shape == "cac_path" and "deck-writer" in url
        ):
            payload_dict["images"] = _image_list
            logger.info(
                "clients.images_attached",
                dept_id=dept_id,
                n_images=len(_image_list),
            )

        try:
            logger.info("clients.query_dispatch", dept_id=dept_id, url=post_url)
            resp = await self._http.post(post_url, json=payload_dict)
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
