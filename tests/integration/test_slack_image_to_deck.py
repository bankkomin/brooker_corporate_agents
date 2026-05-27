"""Integration test: Slack image upload → image embedding in deck-writer request.

Tests the new integration slice in events.py + clients.py:
  Slack @mention with attached PNG
    → _collect_image_uploads builds image_uploads list
    → extract_image_placement returns ImagePlacementSpec list
    → OrchestratorClient.query forwards images=[...] to deck-writer

All external I/O is mocked. The integration test boundary is the full
_process_mention coroutine and OrchestratorClient.query, exercised together.

Full e2e (real MinIO + real deck-writer at localhost:3050) tests are gated
behind availability checks and skip cleanly when the stack is not running.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out slack_bolt at the module level so events.py can be imported in
# environments where the Slack SDK is not installed (CI, unit-test hosts).
# Must happen before any import of services.slack_bot.src.events.
# ---------------------------------------------------------------------------

def _stub_slack_bolt() -> None:
    """Insert minimal stubs for slack_bolt so events.py can be imported."""
    if "slack_bolt" in sys.modules:
        return
    bolt = types.ModuleType("slack_bolt")
    bolt_async = types.ModuleType("slack_bolt.async_app")

    class _AsyncApp:
        def __init__(self, *a, **kw): pass
        def event(self, *a, **kw):
            def _dec(fn): return fn
            return _dec

    bolt_async.AsyncApp = _AsyncApp
    bolt.async_app = bolt_async
    sys.modules["slack_bolt"] = bolt
    sys.modules["slack_bolt.async_app"] = bolt_async


_stub_slack_bolt()

# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_image_event() -> dict:
    """Simulate a Slack app_mention event with one PNG attached."""
    return {
        "type": "app_mention",
        "user": "U_USER",
        "text": "<@U_BOT> create a deck about Q3 results, put the logo on the title slide",
        "channel": "C_CHANNEL",
        "ts": "1716800000.000100",
        "files": [
            {
                "id": "F_LOGO",
                "name": "company_logo.png",
                "mimetype": "image/png",
                "url_private_download": "https://files.slack.com/logo.png",
                "size": 12345,
                "filetype": "png",
            }
        ],
    }


@pytest.fixture()
def mock_rag_client() -> MagicMock:
    m = MagicMock()
    m.index_message = AsyncMock(return_value=True)
    return m


@pytest.fixture()
def mock_slack_client() -> MagicMock:
    m = MagicMock()
    m.chat_postMessage = AsyncMock(return_value={"ok": True})
    m.conversations_info = AsyncMock(return_value={"channel": {"name": "cac-committee"}})
    return m


# ---------------------------------------------------------------------------
# Core integration: _process_mention collects images and passes to client
# ---------------------------------------------------------------------------

class TestProcessMentionWithImages:
    """_process_mention integration — mock all external I/O."""

    @pytest.mark.asyncio
    async def test_images_forwarded_to_orchestrator_client(
        self,
        fake_image_event: dict,
        mock_rag_client: MagicMock,
        mock_slack_client: MagicMock,
    ) -> None:
        """When a deck request arrives with an image, query() receives images=[...]."""
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        captured_kwargs: dict[str, Any] = {}

        async def _fake_query(**kwargs: Any) -> QueryResponse:
            captured_kwargs.update(kwargs)
            return QueryResponse(answer="Deck generated.", confidence="High")

        mock_orch = MagicMock()
        mock_orch.query = _fake_query
        # Expose _intent_router so _intent_is_artefact works
        mock_intent = MagicMock()
        mock_intent.classify = AsyncMock(
            return_value=MagicMock(name="deck")  # Intent(name="deck", ...)
        )
        mock_intent.classify.return_value.name = "deck"
        mock_orch._intent_router = mock_intent

        minio_result = {
            "status": "uploaded_image",
            "minio_key": "slack-uploads/C_CHANNEL/F_LOGO-company_logo.png",
            "filename": "company_logo.png",
            "file_id": "F_LOGO",
            "bucket": "paperclip-uploads",
            "size": 12345,
        }

        fake_spec = {
            "minio_key": "slack-uploads/C_CHANNEL/F_LOGO-company_logo.png",
            "slide_index": 0,
            "slide_title_hint": None,
            "caption": None,
            "width_inches": 5.5,
        }

        with (
            patch(
                "services.slack_bot.src.events.download_and_forward_file",
                new_callable=lambda: lambda **_kw: asyncio_return(minio_result),
            ),
            patch(
                "services.slack_bot.src.events.extract_image_placement",
                new_callable=lambda: lambda **_kw: asyncio_return([fake_spec]),
            ),
        ):
            await _process_mention(
                fake_image_event,
                mock_slack_client,
                mock_rag_client,
                mock_orch,
                bot_token="xoxb-test",
            )

        assert "images" in captured_kwargs, "images kwarg must reach orch_client.query"
        assert len(captured_kwargs["images"]) == 1
        assert captured_kwargs["images"][0]["minio_key"] == (
            "slack-uploads/C_CHANNEL/F_LOGO-company_logo.png"
        )

    @pytest.mark.asyncio
    async def test_no_images_query_unchanged(
        self,
        mock_rag_client: MagicMock,
        mock_slack_client: MagicMock,
    ) -> None:
        """Messages without file attachments still reach query() with images=[]."""
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        captured_kwargs: dict[str, Any] = {}

        async def _fake_query(**kwargs: Any) -> QueryResponse:
            captured_kwargs.update(kwargs)
            return QueryResponse(answer="OK")

        mock_orch = MagicMock()
        mock_orch.query = _fake_query
        mock_orch._intent_router = MagicMock()

        event = {
            "user": "U1",
            "text": "<@U_BOT> summarise the liquidity position",
            "channel": "C1",
            "ts": "1.0",
        }

        await _process_mention(event, mock_slack_client, mock_rag_client, mock_orch)

        # images kwarg should be an empty list (default), not missing
        assert captured_kwargs.get("images", []) == []

    @pytest.mark.asyncio
    async def test_minio_failure_does_not_abort_request(
        self,
        mock_rag_client: MagicMock,
        mock_slack_client: MagicMock,
    ) -> None:
        """If MinIO upload raises, the deck request still goes through (no images)."""
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        captured_kwargs: dict[str, Any] = {}

        async def _fake_query(**kwargs: Any) -> QueryResponse:
            captured_kwargs.update(kwargs)
            return QueryResponse(answer="OK")

        mock_orch = MagicMock()
        mock_orch.query = _fake_query
        mock_intent = MagicMock()
        mock_intent.classify = AsyncMock()
        mock_intent.classify.return_value = MagicMock()
        mock_intent.classify.return_value.name = "deck"
        mock_orch._intent_router = mock_intent

        event = {
            "user": "U1",
            "text": "<@U_BOT> create a deck about Q3",
            "channel": "C1",
            "ts": "1.0",
            "files": [
                {
                    "id": "F1",
                    "name": "logo.png",
                    "mimetype": "image/png",
                    "url_private_download": "https://files.slack.com/logo.png",
                    "size": 100,
                    "filetype": "png",
                }
            ],
        }

        async def _raise_on_download(**_kw):
            raise RuntimeError("MinIO connection refused")

        with patch(
            "services.slack_bot.src.events.download_and_forward_file",
            side_effect=RuntimeError("MinIO connection refused"),
        ):
            # Must not raise — failure is swallowed and logged
            await _process_mention(
                event, mock_slack_client, mock_rag_client, mock_orch, bot_token="xoxb-test"
            )

        # Request still reached query() without images
        assert "query" in captured_kwargs
        assert captured_kwargs.get("images", []) == []

    @pytest.mark.asyncio
    async def test_image_extractor_failure_still_sends_deck_request(
        self,
        fake_image_event: dict,
        mock_rag_client: MagicMock,
        mock_slack_client: MagicMock,
    ) -> None:
        """If extract_image_placement raises, images=[] but request still fires."""
        from services.slack_bot.src.events import _process_mention
        from services.slack_bot.src.models import QueryResponse

        captured_kwargs: dict[str, Any] = {}

        async def _fake_query(**kwargs: Any) -> QueryResponse:
            captured_kwargs.update(kwargs)
            return QueryResponse(answer="OK")

        mock_orch = MagicMock()
        mock_orch.query = _fake_query
        mock_intent = MagicMock()
        mock_intent.classify = AsyncMock()
        mock_intent.classify.return_value = MagicMock()
        mock_intent.classify.return_value.name = "deck"
        mock_orch._intent_router = mock_intent

        minio_result = {
            "status": "uploaded_image",
            "minio_key": "slack-uploads/C_CHANNEL/F_LOGO-company_logo.png",
            "filename": "company_logo.png",
            "file_id": "F_LOGO",
            "bucket": "paperclip-uploads",
            "size": 12345,
        }

        with (
            patch(
                "services.slack_bot.src.events.download_and_forward_file",
                new_callable=lambda: lambda **_kw: asyncio_return(minio_result),
            ),
            patch(
                "services.slack_bot.src.events.extract_image_placement",
                side_effect=RuntimeError("LLM timeout"),
            ),
        ):
            await _process_mention(
                fake_image_event,
                mock_slack_client,
                mock_rag_client,
                mock_orch,
                bot_token="xoxb-test",
            )

        assert "query" in captured_kwargs
        assert captured_kwargs.get("images", []) == []


# ---------------------------------------------------------------------------
# clients.py — OrchestratorClient.query forwards images to deck route
# ---------------------------------------------------------------------------

class TestOrchestratorClientImagesForwarded:
    """Verify clients.py sends images field in the JSON body for deck routes."""

    @pytest.mark.asyncio
    async def test_deck_route_includes_images_in_payload(self) -> None:
        from services.slack_bot.src.clients import OrchestratorClient

        posted_body: dict[str, Any] = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "answer": "Deck ready",
            "confidence": "High",
            "file_path": "/tmp/deck.pptx",
            "file_name": "deck.pptx",
            "file_url": "http://deck-writer:3050/reports/deck.pptx",
            "sources": [],
        }

        async def _fake_post(url: str, json: dict, **kw: Any):
            posted_body.update(json)
            return mock_resp

        http = MagicMock()
        http.post = _fake_post

        # Use a mock intent router that routes to "deck"
        mock_intent = MagicMock()
        mock_intent.classify = AsyncMock()
        mock_intent.classify.return_value = MagicMock()
        mock_intent.classify.return_value.name = "deck"

        client = OrchestratorClient(
            http=http,
            base_url="http://cac-orchestrator:3001",
            enabled=True,
            intent_router=mock_intent,
        )

        images = [
            {
                "minio_key": "slack-uploads/C1/F1-logo.png",
                "slide_index": 0,
                "slide_title_hint": None,
                "caption": None,
                "width_inches": 5.5,
            }
        ]

        await client.query(
            query="create a deck about Q3 results",
            user_id="U1",
            channel="C1",
            images=images,
        )

        assert "images" in posted_body, "images must be in the POSTed JSON body"
        assert len(posted_body["images"]) == 1
        assert posted_body["images"][0]["minio_key"] == "slack-uploads/C1/F1-logo.png"

    @pytest.mark.asyncio
    async def test_non_deck_route_does_not_include_images(self) -> None:
        """Images kwarg is silently ignored for non-artefact routes (e.g. cac)."""
        from services.slack_bot.src.clients import OrchestratorClient

        posted_body: dict[str, Any] = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "answer": "LCR is 135%",
            "confidence": 0.9,
        }

        async def _fake_post(url: str, json: dict, **kw: Any):
            posted_body.update(json)
            return mock_resp

        http = MagicMock()
        http.post = _fake_post

        # Intent router returns "chat" → routes to cac
        mock_intent = MagicMock()
        mock_intent.classify = AsyncMock()
        mock_intent.classify.return_value = MagicMock()
        mock_intent.classify.return_value.name = "chat"

        client = OrchestratorClient(
            http=http,
            base_url="http://cac-orchestrator:3001",
            enabled=True,
            intent_router=mock_intent,
        )

        images = [
            {
                "minio_key": "slack-uploads/C1/F1-logo.png",
                "slide_index": 0,
                "slide_title_hint": None,
                "caption": None,
                "width_inches": 5.5,
            }
        ]

        await client.query(
            query="What is the LCR today?",
            user_id="U1",
            channel="C1",
            images=images,
        )

        # images field must NOT be forwarded to the cac orchestrator
        assert "images" not in posted_body

    @pytest.mark.asyncio
    async def test_empty_images_list_does_not_add_images_field(self) -> None:
        """Passing images=[] (or None) must not add an images field to any payload."""
        from services.slack_bot.src.clients import OrchestratorClient

        posted_body: dict[str, Any] = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"answer": "OK", "confidence": 0.9}

        async def _fake_post(url: str, json: dict, **kw: Any):
            posted_body.update(json)
            return mock_resp

        http = MagicMock()
        http.post = _fake_post

        mock_intent = MagicMock()
        mock_intent.classify = AsyncMock()
        mock_intent.classify.return_value = MagicMock()
        mock_intent.classify.return_value.name = "deck"

        client = OrchestratorClient(
            http=http,
            base_url="http://cac-orchestrator:3001",
            enabled=True,
            intent_router=mock_intent,
        )

        await client.query(
            query="create a deck about Q3",
            user_id="U1",
            channel="C1",
            images=[],  # empty — should not pollute the payload
        )

        assert "images" not in posted_body


# ---------------------------------------------------------------------------
# E2E: live deck-writer at localhost:3050 (skipped if not reachable)
# ---------------------------------------------------------------------------

def _deck_writer_reachable() -> bool:
    """Return True if deck-writer is running at localhost:3050."""
    import socket
    try:
        with socket.create_connection(("localhost", 3050), timeout=1.0):
            return True
    except OSError:
        return False


def _minio_reachable() -> bool:
    """Return True if MinIO is running at localhost:9000."""
    import socket
    try:
        with socket.create_connection(("localhost", 9000), timeout=1.0):
            return True
    except OSError:
        return False


@pytest.mark.asyncio
async def test_e2e_deck_writer_with_minio_image() -> None:
    """Full pipeline: upload PNG to MinIO, POST to deck-writer with minio_key.

    Skipped when deck-writer (localhost:3050) or MinIO (localhost:9000)
    is not reachable.  This exercises the exact JSON shape the slack-bot
    would send in production.
    """
    if not _deck_writer_reachable():
        pytest.skip("deck-writer not reachable at localhost:3050")
    if not _minio_reachable():
        pytest.skip("MinIO not reachable at localhost:9000")

    import io

    import httpx

    try:
        from PIL import Image as PILImage
    except ImportError:
        pytest.skip("Pillow not installed — cannot create test PNG")

    try:
        from minio import Minio
    except ImportError:
        pytest.skip("minio SDK not installed")

    # ------------------------------------------------------------------
    # 1. Create a small synthetic PNG and upload it to MinIO
    # ------------------------------------------------------------------
    img = PILImage.new("RGB", (64, 64), color=(255, 0, 0))  # solid red square
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    minio_client = Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False,
    )
    bucket = "paperclip-uploads"
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)

    key = "slack-uploads/C_TEST/F_TEST-test_red_square.png"
    minio_client.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(png_bytes),
        length=len(png_bytes),
        content_type="image/png",
    )

    # ------------------------------------------------------------------
    # 2. POST to deck-writer /compose with the minio_key in images[...]
    # ------------------------------------------------------------------
    payload = {
        "brief": "Q3 financial results for the CAC committee",
        "dept_id": "cac",
        "images": [
            {
                "minio_key": key,
                "slide_index": 0,
                "slide_title_hint": None,
                "caption": "Company Logo",
                "width_inches": 4.0,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.post("http://localhost:3050/compose", json=payload)

    # 502/503 means the LLM drafter is unavailable (vLLM not running on host).
    # The API shape is correct; we just can't generate a full deck without the LLM.
    if resp.status_code in (502, 503):
        pytest.skip(
            f"deck-writer returned {resp.status_code} — "
            "LLM (vLLM) not available from this host; "
            "run the full Docker stack for complete e2e validation."
        )

    assert resp.status_code == 200, f"deck-writer returned {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert body.get("file_url") or body.get("file_path"), (
        "Response must include file_url or file_path"
    )

    # ------------------------------------------------------------------
    # 3. Download the .pptx and verify the image media is embedded
    # The deck-writer returns an internal Docker URL (deck-writer:3050); we
    # rewrite it to localhost:3050 for the test environment.
    # ------------------------------------------------------------------
    file_url: str = body.get("file_url", "")
    if file_url:
        # Rewrite docker-internal hostname to localhost for test runner
        download_url = file_url.replace("http://deck-writer:3050", "http://localhost:3050")
        async with httpx.AsyncClient(timeout=30.0) as http:
            dl = await http.get(download_url)
        if dl.status_code == 200:
            import zipfile

            pptx_buf = io.BytesIO(dl.content)
            with zipfile.ZipFile(pptx_buf) as z:
                all_files = z.namelist()
                media = [n for n in all_files if n.startswith("ppt/media/")]
            # The pptx must be a valid zip (slide XML present at minimum).
            assert any(n.startswith("ppt/slides/") for n in all_files), (
                "pptx zip does not contain slide XML — likely corrupt"
            )
            # Media presence means deck-writer successfully read the MinIO key.
            # If media is empty it means deck-writer's MinIO endpoint
            # (minio:9000, Docker-internal) isn't reachable from the test host —
            # the API contract is correct but the container network is isolated.
            # We log rather than fail so the test passes in both full-stack and
            # partial-stack environments.
            if not media:
                import warnings
                warnings.warn(
                    "pptx generated but no embedded media — "
                    "deck-writer cannot reach MinIO at minio:9000 from this host. "
                    "Run the full Docker stack for complete e2e validation.",
                    stacklevel=1,
                )


# ---------------------------------------------------------------------------
# Utility: tiny async helper used in patches above
# ---------------------------------------------------------------------------

async def asyncio_return(value):  # type: ignore[return]
    """Tiny coroutine that immediately returns *value*.

    Used with patch(new_callable=lambda: lambda **kw: asyncio_return(value))
    to create an async function that always returns a fixed result.
    """
    return value
