"""Context retrieval node — searches Qdrant per request.

Collections searched per query (resolved from `config/departments.json`):
  own:        {dept_id}_docs, {dept_id}_chat, {dept_id}_knowledge
  shared:     shared_policies
  cross-read: {other_dept}_docs for each dept in crossReadAccess (or all
              live depts when crossReadAccess is ["*"]).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from ..tools.rag_client import RAGClient

logger = structlog.get_logger("cac-orchestrator.retrieve")

# Per-orchestrator default dept; can be overridden via state["dept_id"].
_DEFAULT_DEPT_ID = "cac"

# Cache loaded departments.json so we re-read only when the file changes.
_DEPTS_CACHE: dict[str, dict] | None = None
_DEPTS_CACHE_MTIME: float = 0.0


def _load_departments() -> dict[str, dict]:
    """Read and cache config/departments.json."""
    global _DEPTS_CACHE, _DEPTS_CACHE_MTIME
    from ..config import settings
    config_path = Path(settings.departments_config_path)
    if not config_path.is_file():
        logger.error("departments_json_not_found", path=str(config_path))
        return {}
    mtime = config_path.stat().st_mtime
    if _DEPTS_CACHE is None or mtime != _DEPTS_CACHE_MTIME:
        with config_path.open(encoding="utf-8") as f:
            data = json.load(f)
        _DEPTS_CACHE = data.get("departments", {}) or {}
        _DEPTS_CACHE_MTIME = mtime
    return _DEPTS_CACHE


def _build_collection_list(dept_id: str) -> list[str]:
    """Resolve the full Qdrant collection list this dept may read from."""
    depts = _load_departments()
    dept_cfg = depts.get(dept_id, {}) or {}
    cross = dept_cfg.get("crossReadAccess", []) or []

    own = [f"{dept_id}_docs", f"{dept_id}_chat", f"{dept_id}_knowledge"]
    shared = ["shared_policies"]

    if "*" in cross:
        # wildcard: every other live dept
        other = [k for k, v in depts.items() if k != dept_id and v.get("live", False)]
    else:
        other = list(cross)
    # Cross-read both raw docs AND the compiled wiki knowledge of the other dept,
    # so e.g. CAC can surface CEO strategy (Khao Yai resolutions live in
    # ceo_knowledge, not ceo_docs).
    cross_collections = [f"{d}_docs" for d in other] + [f"{d}_knowledge" for d in other]

    return own + shared + cross_collections


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
    dept_id = state.get("dept_id") or _DEFAULT_DEPT_ID
    collections = _build_collection_list(dept_id)

    if embed_fn is not None:
        query_vector = await embed_fn(query)
    else:
        # Fallback: zero vector (for testing without embedder)
        query_vector = [0.0] * 384
        logger.warning("no_embed_fn_provided", using="zero_vector")

    results = await rag_client.search(
        query_vector=query_vector,
        collections=collections,
        top_k=top_k,
        min_relevance=min_relevance,
    )

    context_parts: list[str] = []
    for i, r in enumerate(results, 1):
        source_label = f"[{i}] {r.get('filename', 'unknown')}"
        if r.get("page"):
            source_label += f" p.{r['page']}"
        context_parts.append(f"{source_label}: {r.get('excerpt', '')}")

    context_text = "\n\n".join(context_parts) if context_parts else ""
    logger.info(
        "context_retrieved",
        dept_id=dept_id,
        source_count=len(results),
        collections=len(collections),
    )
    return {"sources": results, "context_text": context_text}
