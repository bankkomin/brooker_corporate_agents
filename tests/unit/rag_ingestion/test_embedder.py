"""Tests for vLLM embedder wrapper."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from services.rag_ingestion.src.embedder import Embedder

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.vllm_embed_url = "http://localhost:8002/v1"
    s.vllm_embed_model = "qwen-embed"
    return s


@pytest.fixture
def embedder(settings: MagicMock) -> Embedder:
    return Embedder(settings)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embed_response(texts: list[str], dim: int = 4) -> dict:
    """Build a mock OpenAI-compatible embedding response."""
    return {
        "data": [
            {"embedding": [0.1 * (i + 1)] * dim, "index": i}
            for i in range(len(texts))
        ]
    }


def _mock_http_post(texts: list[str], dim: int = 4) -> AsyncMock:
    """Return a mock AsyncClient whose post() yields a valid embedding response."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = _make_embed_response(texts, dim=dim)

    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.post.return_value = mock_resp
    return mock_http


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestEmbedderInit:
    def test_url_constructed_correctly(self, settings: MagicMock) -> None:
        """URL must end with /embeddings, not double-slash."""
        e = Embedder(settings)
        assert e._url == "http://localhost:8002/v1/embeddings"

    def test_url_strips_trailing_slash(self) -> None:
        """Trailing slash on vllm_embed_url must be removed before appending /embeddings."""
        s = MagicMock()
        s.vllm_embed_url = "http://localhost:8002/v1/"
        s.vllm_embed_model = "qwen-embed"
        e = Embedder(s)
        assert e._url == "http://localhost:8002/v1/embeddings"

    def test_http_client_initially_none(self, embedder: Embedder) -> None:
        assert embedder._http is None

    def test_batch_size_default(self, embedder: Embedder) -> None:
        assert embedder.BATCH_SIZE == 32


# ---------------------------------------------------------------------------
# start / close lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_start_creates_http_client(self, embedder: Embedder) -> None:
        await embedder.start()
        assert embedder._http is not None
        await embedder.close()

    async def test_close_sets_http_to_none(self, embedder: Embedder) -> None:
        await embedder.start()
        await embedder.close()
        assert embedder._http is None

    async def test_close_is_safe_when_not_started(self, embedder: Embedder) -> None:
        """close() must not raise when _http is None."""
        await embedder.close()  # should not raise

    async def test_start_then_close_calls_aclose(self, embedder: Embedder) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        embedder._http = mock_http
        await embedder.close()
        mock_http.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# embed_texts
# ---------------------------------------------------------------------------


class TestEmbedTexts:
    async def test_empty_list_returns_empty(self, embedder: Embedder) -> None:
        result = await embedder.embed_texts([])
        assert result == []

    async def test_single_text_returns_one_vector(self, embedder: Embedder) -> None:
        embedder._http = _mock_http_post(["hello"], dim=4)
        result = await embedder.embed_texts(["hello"])
        assert len(result) == 1
        assert len(result[0]) == 4

    async def test_multiple_texts_within_one_batch(self, embedder: Embedder) -> None:
        texts = ["alpha", "beta", "gamma"]
        embedder._http = _mock_http_post(texts, dim=8)
        result = await embedder.embed_texts(texts)
        assert len(result) == 3
        assert all(len(v) == 8 for v in result)

    async def test_batch_splitting_calls_post_multiple_times(
        self, embedder: Embedder
    ) -> None:
        """With BATCH_SIZE=2 and 3 texts, _embed_batch must be called twice."""
        embedder.BATCH_SIZE = 2
        texts = ["a", "b", "c"]

        call_count = 0

        async def _post(url: str, json: dict) -> MagicMock:
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = _make_embed_response(json["input"])
            return resp

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.side_effect = _post
        embedder._http = mock_http

        result = await embedder.embed_texts(texts)
        assert len(result) == 3
        assert call_count == 2  # batch [a,b] + batch [c]

    async def test_results_ordered_by_index(self, embedder: Embedder) -> None:
        """Response items may arrive out-of-order; result must follow input order."""
        # Return data with reversed index ordering
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"embedding": [0.2, 0.2], "index": 1},
                {"embedding": [0.1, 0.1], "index": 0},
            ]
        }
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_resp
        embedder._http = mock_http

        result = await embedder.embed_texts(["first", "second"])
        assert result[0] == [0.1, 0.1]  # index 0
        assert result[1] == [0.2, 0.2]  # index 1

    async def test_payload_includes_model_name(self, embedder: Embedder) -> None:
        """POST body must contain the configured model name."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_embed_response(["test"])

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_resp
        embedder._http = mock_http

        await embedder.embed_texts(["test"])
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["model"] == "qwen-embed"

    async def test_http_error_propagates(self, embedder: Embedder) -> None:
        """HTTPStatusError from raise_for_status must bubble up."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_resp
        embedder._http = mock_http

        # HTTPStatusError is not in the tenacity retry set, so it raises immediately
        with pytest.raises(httpx.HTTPStatusError):
            await embedder.embed_texts(["fail"])

    async def test_assert_error_when_http_not_started(
        self, embedder: Embedder
    ) -> None:
        """Calling embed_texts without start() must raise AssertionError."""
        with pytest.raises(AssertionError, match="Call start()"):
            await embedder.embed_texts(["no client"])


# ---------------------------------------------------------------------------
# embed_single
# ---------------------------------------------------------------------------


class TestEmbedSingle:
    async def test_returns_first_vector(self, embedder: Embedder) -> None:
        embedder._http = _mock_http_post(["hello"], dim=6)
        result = await embedder.embed_single("hello")
        assert len(result) == 6
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    async def test_delegates_to_embed_texts(self, embedder: Embedder) -> None:
        """embed_single must call embed_texts with a one-element list."""
        embedder._http = _mock_http_post(["x"], dim=4)
        with patch.object(
            embedder, "embed_texts", wraps=embedder.embed_texts
        ) as spy:
            await embedder.embed_single("x")
            spy.assert_awaited_once_with(["x"])


# ---------------------------------------------------------------------------
# get_dimension
# ---------------------------------------------------------------------------


class TestGetDimension:
    async def test_returns_vector_length(self, embedder: Embedder) -> None:
        embedder._http = _mock_http_post(["dimension test"], dim=768)
        dim = await embedder.get_dimension()
        assert dim == 768

    async def test_uses_embed_single_probe_text(self, embedder: Embedder) -> None:
        """get_dimension must probe with the exact string 'dimension test'."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = _make_embed_response(["dimension test"], dim=512)
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = mock_resp
        embedder._http = mock_http

        dim = await embedder.get_dimension()
        assert dim == 512
        # Verify the exact probe text was posted
        _, kwargs = mock_http.post.call_args
        assert kwargs["json"]["input"] == ["dimension test"]


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    async def test_healthy_when_models_endpoint_200(
        self, embedder: Embedder
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = mock_resp
        embedder._http = mock_http

        assert await embedder.health_check() is True

    async def test_unhealthy_when_models_endpoint_non_200(
        self, embedder: Embedder
    ) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = mock_resp
        embedder._http = mock_http

        assert await embedder.health_check() is False

    async def test_unhealthy_on_connect_error(self, embedder: Embedder) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.side_effect = httpx.ConnectError("refused")
        embedder._http = mock_http

        assert await embedder.health_check() is False

    async def test_unhealthy_on_timeout(self, embedder: Embedder) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.side_effect = httpx.TimeoutException("timeout")
        embedder._http = mock_http

        assert await embedder.health_check() is False

    async def test_unhealthy_when_http_not_started(
        self, embedder: Embedder
    ) -> None:
        """health_check must return False (not raise) when _http is None."""
        assert embedder._http is None
        result = await embedder.health_check()
        assert result is False

    async def test_health_check_hits_models_endpoint(
        self, embedder: Embedder
    ) -> None:
        """GET must go to /models, not /embeddings."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = mock_resp
        embedder._http = mock_http

        await embedder.health_check()
        called_url = mock_http.get.call_args[0][0]
        assert called_url.endswith("/models")
        assert "embeddings" not in called_url
