# services/rag-ingestion/src/embedder.py
"""Async embedding wrapper — supports Gemini, vLLM-compat HTTP, and a
local sentence-transformer backend.

Backends (selected by `EMBEDDER_TYPE` env var):
  - "gemini"       : Google Gemini text-embedding-001 (cloud, rate-limited)
  - "vllm"         : OpenAI-compat /embeddings endpoint. Use this with the
                     host-native scripts/embed_server.py running on the
                     host's RTX 4060 Ti (recommended — no Docker GPU
                     passthrough needed). Default.
  - "local_gemma"  : sentence-transformers running google/embeddinggemma-300m
                     directly inside this container. Requires CUDA torch +
                     Docker GPU passthrough — not the default.

Default is `vllm` pointed at host.docker.internal:8765 (where the host
embed server lives) to escape Gemini's free-tier rate-limit cascade during
bulk ingest. 300M params, ~600 MB VRAM in FP16.
"""
from __future__ import annotations

import asyncio
import os

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import RAGSettings

logger = structlog.get_logger("rag-ingestion.embedder")


class Embedder:
    """Async embedding client with pluggable backend."""

    BATCH_SIZE = 32           # vLLM batch size
    GEMINI_BATCH_SIZE = 100   # Gemini supports up to 2048 per request
    LOCAL_BATCH_SIZE = 64     # sentence-transformers GPU batch

    def __init__(self, settings: RAGSettings) -> None:
        self._backend = settings.embedder_type.lower()
        self._settings = settings

        # vLLM config
        self._vllm_url = f"{settings.vllm_embed_url.rstrip('/')}/embeddings"
        self._vllm_model = settings.vllm_embed_model

        # Gemini config
        self._gemini_model = settings.gemini_embed_model
        self._gemini_client = None

        # Local (sentence-transformers) config
        self._local_model_name = os.getenv("LOCAL_EMBED_MODEL", "google/embeddinggemma-300m")
        self._local_device = os.getenv("LOCAL_EMBED_DEVICE", "auto")  # "auto" | "cuda" | "cpu"
        self._local_model = None

        self._http: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._backend == "gemini":
            from google import genai
            api_key = self._settings.gemini_api_key
            self._gemini_client = genai.Client(api_key=api_key) if api_key else genai.Client()
            logger.info("embedder.started", backend="gemini", model=self._gemini_model)
        elif self._backend == "local_gemma":
            await self._start_local()
        else:
            self._http = httpx.AsyncClient(timeout=30.0)
            logger.info("embedder.started", backend="vllm", url=self._vllm_url)

    async def _start_local(self) -> None:
        """Load the sentence-transformers model. Slow once on cold start,
        then in-memory. Runs in a thread so we don't block the event loop."""
        from sentence_transformers import SentenceTransformer
        import torch

        if self._local_device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            device = self._local_device
        loop = asyncio.get_event_loop()
        self._local_model = await loop.run_in_executor(
            None,
            lambda: SentenceTransformer(self._local_model_name, device=device),
        )
        vram_gb = None
        if device == "cuda":
            try:
                vram_gb = round(
                    torch.cuda.get_device_properties(0).total_memory / 1e9, 1
                )
            except Exception:
                pass
        logger.info(
            "embedder.started",
            backend="local_gemma",
            model=self._local_model_name,
            device=device,
            vram_gb=vram_gb,
        )

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None
        self._gemini_client = None
        self._local_model = None

    # ── Public API ──────────────────────────────────────────────────

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, splitting into batches."""
        if not texts:
            return []
        if self._backend == "gemini":
            return await self._embed_gemini(texts)
        if self._backend == "local_gemma":
            return await self._embed_local(texts)
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
            if self._backend == "local_gemma":
                return self._local_model is not None
            assert self._http is not None
            resp = await self._http.get(self._vllm_url.replace("/embeddings", "/models"))
            return resp.status_code == 200
        except Exception:
            return False

    # ── Local sentence-transformer backend ──────────────────────────

    async def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Embed via sentence-transformers in-process (GPU or CPU).

        Runs the blocking encode() in a thread so we don't stall the event loop.
        """
        if self._local_model is None:
            raise RuntimeError("local embedder not started; call .start() first")
        loop = asyncio.get_event_loop()

        def _encode() -> list[list[float]]:
            arr = self._local_model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
                batch_size=self.LOCAL_BATCH_SIZE,
            )
            return arr.tolist()

        return await loop.run_in_executor(None, _encode)

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
