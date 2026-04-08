"""Context retrieval node — searches Qdrant across 3 collections."""
from __future__ import annotations

from typing import Any

import structlog

from ..tools.rag_client import RAGClient

logger = structlog.get_logger("cac-orchestrator.retrieve")

COLLECTIONS = ["cac_docs", "cac_chat", "cac_knowledge"]


async def retrieve_context(
    state: dict,
    *,
    rag_client: RAGClient,
    embed_fn: Any = None,  # callable: async (text) -> list[float]
    top_k: int = 8,
    min_relevance: float = 0.70,
) -> dict:
    """Retrieve relevant context from Qdrant.

    Returns {"sources": list[dict], "context_text": str}.
    """
    query = state.get("query", "")

    # Get query embedding
    if embed_fn is not None:
        query_vector = await embed_fn(query)
    else:
        # Fallback: zero vector (for testing without embedder)
        query_vector = [0.0] * 384
        logger.warning("no_embed_fn_provided", using="zero_vector")

    results = await rag_client.search(
        query_vector=query_vector,
        collections=COLLECTIONS,
        top_k=top_k,
        min_relevance=min_relevance,
    )

    # Format context for LLM consumption
    context_parts: list[str] = []
    for i, r in enumerate(results, 1):
        source_label = f"[{i}] {r.get('filename', 'unknown')}"
        if r.get("page"):
            source_label += f" p.{r['page']}"
        context_parts.append(f"{source_label}: {r.get('excerpt', '')}")

    context_text = "\n\n".join(context_parts) if context_parts else ""
    logger.info("context_retrieved", source_count=len(results))
    return {"sources": results, "context_text": context_text}
