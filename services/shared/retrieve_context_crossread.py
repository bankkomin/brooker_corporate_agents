"""Extended retrieve_context with cross-department read access and graceful degradation."""
import logging
from typing import Any

log = logging.getLogger(__name__)

_warned_collections: set[str] = set()


async def retrieve_context_with_crossread(
    query: str,
    dept_config: dict,
    qdrant_client: Any,
    embedding_fn: Any = None,
    top_k: int = 5,
    db_conn: Any = None,
) -> list:
    """Retrieve context from own collections + cross-read collections.

    Args:
        query: The search query
        dept_config: Department config dict with dept_id and crossReadAccess
        qdrant_client: Qdrant async client
        embedding_fn: Async function to embed query text
        top_k: Max results to return
        db_conn: Optional DB connection for knowledge gap writing
    """
    dept_id = dept_config["dept_id"]
    cross = dept_config.get("crossReadAccess", [])

    # Build collection list with weights
    own_collections = [f"{dept_id}_docs", f"{dept_id}_chat", f"{dept_id}_knowledge"]
    shared_collections = ["shared_policies"]
    cross_collections = []

    if "*" in cross:
        # Legal + CEO pattern: read all known department doc collections
        import json as _json
        from pathlib import Path as _Path
        try:
            cfg_path = _Path("/app/config/departments.json")
            if cfg_path.exists():
                data = _json.loads(cfg_path.read_text())
                depts = data.get("departments", {})
                if isinstance(depts, dict):
                    all_dept_ids = [k for k in depts.keys() if k != dept_id]
                else:
                    all_dept_ids = [d["dept_id"] for d in depts if d.get("dept_id") != dept_id]
                cross_collections = [f"{d}_docs" for d in all_dept_ids]
            else:
                log.warning("Wildcard crossread: departments.json not found, no cross-dept collections loaded")
        except Exception:
            log.exception("Failed to resolve wildcard crossReadAccess")
    else:
        cross_collections = [f"{d}_docs" for d in cross]

    all_collections = own_collections + shared_collections + cross_collections
    weights = {}
    for c in all_collections:
        if c.startswith(dept_id):
            weights[c] = 1.0
        elif c == "shared_policies":
            weights[c] = 0.7
        else:
            weights[c] = 0.4

    # Embed query if embedding function provided
    query_vector = None
    if embedding_fn:
        query_vector = await embedding_fn(query)

    # Search all collections with graceful degradation
    hits = []
    total_hit_count = 0

    for collection in all_collections:
        try:
            if query_vector is not None:
                results = await qdrant_client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=top_k,
                )
            else:
                results = []

            weight = weights.get(collection, 0.4)
            for hit in results:
                hit.score = hit.score * weight
                hits.append(hit)
            total_hit_count += len(results)

        except Exception as e:
            # Graceful degradation: log once per missing collection
            if collection not in _warned_collections:
                log.info("Collection %s unavailable, skipping (%s: %s)", collection, type(e).__name__, e)
                _warned_collections.add(collection)

    # Sort by weighted score
    hits.sort(key=lambda h: h.score, reverse=True)
    result = hits[:top_k]

    # Knowledge gap tracking: write row when total hits < 3
    if total_hit_count < 3 and db_conn is not None:
        try:
            await db_conn.execute(
                """INSERT INTO agent_knowledge_gaps (dept_id, agent_id, query, hit_count)
                   VALUES ($1, $2, $3, $4)""",
                dept_id,
                dept_config.get("active_agent", "unknown"),
                query[:500],
                total_hit_count,
            )
        except Exception:
            log.exception("Failed to write knowledge gap")

    return result
