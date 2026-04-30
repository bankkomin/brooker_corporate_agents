"""Context retrieval node — searches Qdrant across 3 collections.

Phase 2: optionally uses cross-department read access via shared library.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from ..tools.rag_client import RAGClient

try:
    from services.shared.retrieve_context_crossread import retrieve_context_with_crossread
except ImportError:
    retrieve_context_with_crossread = None  # type: ignore[assignment]

logger = structlog.get_logger("cac-orchestrator.retrieve")

COLLECTIONS = ["cac_docs", "cac_chat", "cac_knowledge"]

# CAC department config for crossread — loaded once
_CAC_DEPT_CONFIG: dict | None = None


def _load_cac_dept_config() -> dict:
    """Load the CAC department entry from departments.json."""
    global _CAC_DEPT_CONFIG
    if _CAC_DEPT_CONFIG is not None:
        return _CAC_DEPT_CONFIG

    from ..config import settings
    config_path = Path(settings.departments_config_path)
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as f:
            data = json.load(f)
        cac = data.get("departments", {}).get("cac", {})
        _CAC_DEPT_CONFIG = {
            "dept_id": "cac",
            "crossReadAccess": cac.get("crossReadAccess", []),
            "active_agent": "cac-orchestrator",
        }
    else:
        # No hardcoded fallback — agent must not silently operate with stale access rules
        logger.error("departments_json_not_found", path=str(config_path),
                      msg="crossReadAccess defaulting to empty (no cross-dept reads)")
        _CAC_DEPT_CONFIG = {
            "dept_id": "cac",
            "crossReadAccess": [],
            "active_agent": "cac-orchestrator",
        }
    return _CAC_DEPT_CONFIG


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
    Phase 2: attempts crossread retrieval first, falls back to original logic.
    """
    query = state.get("query", "")

    # Phase 2: try cross-department retrieval via shared library
    if retrieve_context_with_crossread is not None:
        try:
            dept_config = _load_cac_dept_config()
            crossread_results = await retrieve_context_with_crossread(
                query=query,
                dept_config=dept_config,
                qdrant_client=rag_client,
                embedding_fn=embed_fn,
                top_k=top_k,
            )

            if crossread_results:
                # Convert Qdrant hit objects to dict format for downstream nodes
                results: list[dict] = []
                for hit in crossread_results:
                    payload = getattr(hit, "payload", {}) or {}
                    results.append({
                        "filename": payload.get("filename", "unknown"),
                        "page": payload.get("page"),
                        "excerpt": payload.get("text", payload.get("excerpt", "")),
                        "relevance_score": getattr(hit, "score", 0.0),
                        "type": payload.get("type", "document"),
                        "date": payload.get("date"),
                        "uploader": payload.get("uploader"),
                    })

                context_parts: list[str] = []
                for i, r in enumerate(results, 1):
                    source_label = f"[{i}] {r.get('filename', 'unknown')}"
                    if r.get("page"):
                        source_label += f" p.{r['page']}"
                    context_parts.append(f"{source_label}: {r.get('excerpt', '')}")

                context_text = "\n\n".join(context_parts) if context_parts else ""
                logger.info(
                    "crossread_context_retrieved",
                    source_count=len(results),
                    collections="crossread",
                )
                return {"sources": results, "context_text": context_text}
        except Exception as exc:
            logger.warning(
                "crossread_retrieve_failed",
                error=str(exc),
                fallback="original_retrieve",
            )

    # Original retrieve logic (fallback)
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
