"""Context retrieval node for HR -- searches HR Qdrant collections + shared_policies.

Phase 2: uses cross-department read access via shared library (with knowledge gap tracking).
HR has crossReadAccess: [] so it only queries its own collections + shared_policies,
but the crossread function adds knowledge gap tracking which is beneficial.
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

logger = structlog.get_logger("hr-orchestrator.retrieve")

HR_COLLECTIONS = ["hr_docs", "hr_chat", "hr_knowledge", "shared_policies"]

# HR department config for crossread -- loaded once
_HR_DEPT_CONFIG: dict | None = None


def _load_hr_dept_config() -> dict:
    """Load the HR department entry from departments.json."""
    global _HR_DEPT_CONFIG
    if _HR_DEPT_CONFIG is not None:
        return _HR_DEPT_CONFIG

    from ..config import settings
    config_path = Path(settings.departments_config_path)
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as f:
            data = json.load(f)
        hr = data.get("departments", {}).get("hr", {})
        _HR_DEPT_CONFIG = {
            "dept_id": "hr",
            "crossReadAccess": hr.get("crossReadAccess", []),
            "active_agent": "hr-orchestrator",
        }
    else:
        # Fallback: HR has no cross-read access
        _HR_DEPT_CONFIG = {
            "dept_id": "hr",
            "crossReadAccess": [],
            "active_agent": "hr-orchestrator",
        }
        logger.warning("departments_json_not_found", path=str(config_path))
    return _HR_DEPT_CONFIG


async def retrieve_context(
    state: dict,
    *,
    rag_client: RAGClient,
    embed_fn: Any = None,
    top_k: int = 8,
    min_relevance: float = 0.70,
) -> dict:
    """Retrieve relevant context from Qdrant.

    Returns {"sources": list[dict], "context_text": str}.
    Phase 2: attempts crossread retrieval first (for knowledge gap tracking),
    falls back to original logic.
    """
    query = state.get("query", "")

    # Phase 2: try cross-department retrieval via shared library
    if retrieve_context_with_crossread is not None:
        try:
            dept_config = _load_hr_dept_config()
            crossread_results = await retrieve_context_with_crossread(
                query=query,
                dept_config=dept_config,
                qdrant_client=rag_client,
                embedding_fn=embed_fn,
                top_k=top_k,
            )

            if crossread_results:
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
    if embed_fn is not None:
        query_vector = await embed_fn(query)
    else:
        query_vector = [0.0] * 384
        logger.warning("no_embed_fn_provided", using="zero_vector")

    results = await rag_client.search(
        query_vector=query_vector,
        collections=HR_COLLECTIONS,
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
