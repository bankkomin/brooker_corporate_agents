"""Local embedding server — OpenAI /embeddings-compatible.

Runs on the HOST (not Docker) so it can use the RTX 4060 Ti directly
without Docker GPU passthrough setup. rag-ingestion (in Docker) calls
this via host.docker.internal:8765.

Why a separate process instead of in-container CUDA torch:
  - No NVIDIA Container Toolkit setup on Windows
  - No 2.5 GB CUDA torch wheel inside rag-ingestion image
  - GPU access just works (native Windows PyTorch + CUDA driver)
  - One Python process owns the model in memory; multiple Docker
    services share it via HTTP

Setup (one-time):
    pip install fastapi uvicorn sentence-transformers torch --upgrade
    # For GPU: install the matching CUDA wheel from pytorch.org

    # If google/embeddinggemma-300m is gated:
    pip install huggingface_hub
    huggingface-cli login  # paste the token from huggingface.co/settings/tokens

Run:
    python scripts/embed_server.py
    # or with options:
    python scripts/embed_server.py --model google/embeddinggemma-300m --port 8765

Tell rag-ingestion to use it by setting in .env:
    EMBEDDER_TYPE=vllm
    VLLM_EMBED_URL=http://host.docker.internal:8765/v1
    VLLM_EMBED_MODEL=local-gemma
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

# UTF-8 stdout so log lines with non-ASCII don't crash on Windows cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("embed-server")

_state: dict[str, Any] = {}


class RerankRequest(BaseModel):
    """Cross-encoder rerank request.

    Given a `query` and a list of `documents`, return per-document relevance
    scores in the original order. The orchestrator can then re-sort retrieval
    results by these scores (more semantically faithful than cosine similarity
    on standalone embeddings).
    """
    query: str
    documents: list[str]
    model: str | None = None  # accepted but ignored; always uses loaded model


class RerankItem(BaseModel):
    index: int
    score: float


class RerankResponse(BaseModel):
    model: str
    results: list[RerankItem]
    latency_ms: float


class EmbeddingsRequest(BaseModel):
    """OpenAI-compatible /embeddings request.

    `model` is accepted but ignored — we always serve the model loaded at
    startup. `input` may be str or list[str], matching the OpenAI spec.
    """
    model: str | None = None
    input: str | list[str]
    # extra fields we accept but ignore
    encoding_format: str | None = None
    user: str | None = None


class EmbeddingItem(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingsResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingItem]
    model: str
    usage: dict[str, int] | None = None


def _load_model(model_name: str, device: str):
    """Load the sentence-transformer. Done in lifespan so server isn't
    serving requests before the model is ready."""
    from sentence_transformers import SentenceTransformer
    import torch

    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"

    log.info("loading model=%s on device=%s ...", model_name, device)
    t0 = time.monotonic()
    model = SentenceTransformer(model_name, device=device)
    elapsed = time.monotonic() - t0
    log.info("model loaded in %.1fs", elapsed)

    if device == "cuda":
        try:
            props = torch.cuda.get_device_properties(0)
            log.info(
                "gpu=%s  vram_total=%.1fGB  vram_used=%.1fGB",
                props.name,
                props.total_memory / 1e9,
                torch.cuda.memory_allocated(0) / 1e9,
            )
        except Exception:
            pass
    return model, device


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_name = os.getenv("EMBED_MODEL", "google/embeddinggemma-300m")
    device = os.getenv("EMBED_DEVICE", "auto")
    model, resolved_device = _load_model(model_name, device)
    _state["model"] = model
    _state["model_name"] = model_name
    _state["device"] = resolved_device
    _state["batch_size"] = int(os.getenv("EMBED_BATCH_SIZE", "64"))
    yield
    _state.clear()


app = FastAPI(title="local embed server", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    if "model" not in _state:
        raise HTTPException(503, "model not loaded yet")
    return {
        "status": "ok",
        "model": _state["model_name"],
        "device": _state["device"],
    }


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    """OpenAI-compat models list. rag-ingestion's health_check pings this."""
    return {
        "object": "list",
        "data": [
            {"id": _state.get("model_name", "unknown"), "object": "model"},
            {"id": "local-gemma", "object": "model"},
        ],
    }


def _do_encode(texts: list[str]) -> list[list[float]]:
    model = _state["model"]
    batch = _state.get("batch_size", 64)
    arr = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
        batch_size=batch,
    )
    return arr.tolist()


def _get_reranker():
    """Lazy-load the cross-encoder on first /rerank call (keeps startup fast)."""
    if "reranker" in _state:
        return _state["reranker"]
    from sentence_transformers import CrossEncoder
    import torch
    name = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    device = _state.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
    log.info("loading reranker=%s on device=%s ...", name, device)
    t0 = time.monotonic()
    model = CrossEncoder(name, device=device, max_length=384)
    log.info("reranker loaded in %.1fs", time.monotonic() - t0)
    _state["reranker"] = model
    _state["reranker_name"] = name
    return model


@app.post("/rerank", response_model=RerankResponse)
async def rerank(req: RerankRequest) -> RerankResponse:
    """Score `documents` by relevance to `query` using a cross-encoder.

    Returns results in INPUT ORDER (caller sorts by score). This is intentionally
    a thin scoring API — the orchestrator's reranker policy (top-K, tie-break,
    minimum score) lives on its side.
    """
    if not req.documents:
        raise HTTPException(400, "documents must be non-empty")
    if len(req.documents) > 64:
        raise HTTPException(400, f"too many documents ({len(req.documents)}); cap is 64")
    model = _get_reranker()
    t0 = time.monotonic()
    pairs = [(req.query, d or "") for d in req.documents]
    scores = model.predict(pairs, batch_size=32, show_progress_bar=False)
    elapsed_ms = (time.monotonic() - t0) * 1000
    return RerankResponse(
        model=_state.get("reranker_name", "cross-encoder"),
        results=[RerankItem(index=i, score=float(s)) for i, s in enumerate(scores)],
        latency_ms=round(elapsed_ms, 1),
    )


@app.post("/v1/embeddings", response_model=EmbeddingsResponse)
@app.post("/embeddings", response_model=EmbeddingsResponse)
async def embeddings(req: EmbeddingsRequest) -> EmbeddingsResponse:
    if "model" not in _state:
        raise HTTPException(503, "model not loaded yet")

    if isinstance(req.input, str):
        texts = [req.input]
    else:
        texts = list(req.input)
    if not texts:
        return EmbeddingsResponse(data=[], model=_state["model_name"], usage={"total_tokens": 0})

    import asyncio
    loop = asyncio.get_event_loop()
    t0 = time.monotonic()
    vecs = await loop.run_in_executor(None, _do_encode, texts)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "embedded n=%d avg_chars=%d elapsed_ms=%d",
        len(texts), sum(len(t) for t in texts) // max(1, len(texts)), elapsed_ms,
    )
    return EmbeddingsResponse(
        data=[EmbeddingItem(index=i, embedding=v) for i, v in enumerate(vecs)],
        model=_state["model_name"],
        usage={"total_tokens": sum(len(t.split()) for t in texts)},
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--model", default=os.getenv("EMBED_MODEL", "google/embeddinggemma-300m"))
    p.add_argument("--device", default=os.getenv("EMBED_DEVICE", "auto"),
                   help="auto | cuda | cpu")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.getenv("EMBED_PORT", "8765")))
    p.add_argument("--batch-size", type=int, default=64)
    args = p.parse_args()

    os.environ["EMBED_MODEL"] = args.model
    os.environ["EMBED_DEVICE"] = args.device
    os.environ["EMBED_BATCH_SIZE"] = str(args.batch_size)

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
