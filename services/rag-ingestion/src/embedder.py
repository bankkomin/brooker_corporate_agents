# services/rag-ingestion/src/embedder.py
"""Async embedding wrapper — supports Gemini and vLLM backends."""
from __future__ import annotations

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import RAGSettings

logger = structlog.get_logger("rag-ingestion.embedder")


class Embedder:
    """Async embedding client with pluggable backend (gemini or vllm)."""

    BATCH_SIZE = 32  # vLLM batch size
    GEMINI_BATCH_SIZE = 100  # Gemini supports up to 2048 per request

    def __init__(self, settings: RAGSettings) -> None:
        self._backend = settings.embedder_type.lower()
        self._settings = settings

        # vLLM config
        self._vllm_url = f"{settings.vllm_embed_url.rstrip('/')}/embeddings"
        self._vllm_model = settings.vllm_embed_model

        # Gemini config
        self._gemini_model = settings.gemini_embed_model
        self._gemini_client = None

        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._backend == "gemini":
            from google import genai
            api_key = self._settings.gemini_api_key
            self._gemini_client = genai.Client(api_key=api_key) if api_key else genai.Client()
            logger.info("embedder.started", backend="gemini", model=self._gemini_model)
        else:
            self._http = httpx.AsyncClient(timeout=30.0)
            logger.info("embedder.started", backend="vllm", url=self._vllm_url)

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None
        self._gemini_client = None

    # ── Public API ──────────────────────────────────────────────────

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, splitting into batches."""
        if not texts:
            return []
        if self._backend == "gemini":
            return await self._embed_gemini(texts)
        return await self._embed_vllm(texts)

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text string."""
        results = await self.embed_texts([text])
        return results[0]

    async def get_dimension(self) -> int:
        """Get embedding dimension by embedding a test string."""
        vec = await self.embed_single("dimension test")
        return len(vec)

    async def health_check(self) -> bool:
        """Check if the embedding backend is reachable."""
        try:
            if self._backend == "gemini":
                vec = await self.embed_single("health")
                return len(vec) > 0
            assert self._http is not None
            resp = await self._http.get(self._vllm_url.replace("/embeddings", "/models"))
            return resp.status_code == 200
        except Exception:
            return False

    # ── Gemini backend ──────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _gemini_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch via Gemini API."""
        assert self._gemini_client is not None, "Call start() before embedding"
        result = await self._gemini_client.aio.models.embed_content(
            model=self._gemini_model,
            contents=texts,
        )
        return [e.values for e in result.embeddings]

    async def _embed_gemini(self, texts: list[str]) -> list[list[float]]:
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.GEMINI_BATCH_SIZE):
            batch = texts[i : i + self.GEMINI_BATCH_SIZE]
            vectors = await self._gemini_batch(batch)
            all_vectors.extend(vectors)
            logger.debug("embedder.gemini_batch_done", batch_start=i, count=len(batch))
        return all_vectors

    # ── vLLM backend ────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _vllm_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch via vLLM (OpenAI-compatible endpoint)."""
        assert self._http is not None, "Call start() before embedding"
        payload = {"model": self._vllm_model, "input": texts}
        resp = await self._http.post(self._vllm_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        sorted_results = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_results]

    async def _embed_vllm(self, texts: list[str]) -> list[list[float]]:
        all_vectors: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            vectors = await self._vllm_batch(batch)
            all_vectors.extend(vectors)
            logger.debug("embedder.vllm_batch_done", batch_start=i, count=len(batch))
        return all_vectors
