"""RAG client for Qdrant vector search."""
from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger("cac-orchestrator.rag")


class RAGClient:
    """Async client for Qdrant REST API search."""

    def __init__(self, host: str, port: int, timeout: float = 10.0) -> None:
        self._base_url = f"http://{host}:{port}"
        self._client = httpx.AsyncClient(timeout=timeout)

    async def search(
        self,
        query_vector: list[float],
        collections: list[str],
        top_k: int = 16,
        min_relevance: float = 0.35,
    ) -> list[dict]:
        """Round-robin search across multiple Qdrant collections.

        Why round-robin instead of global sort: shared_policies has ~811k chunks
        vs ~100-3000 in dept-specific collections; its top scores dominate a
        global sort even when dept-specific fact-chunks (e.g. "DBS Bank" in
        vcc_knowledge, "164.6554 BTC" in cio_knowledge) are well within that
        collection's top-K. Round-robin guarantees the LLM sees dept-relevant
        context. Defaults: top_k=16 (was 8), min_relevance=0.35 (was 0.70 — most
        fact-chunks score 0.40-0.55 against real-world queries).
        """
        PER_COL = 8
        results_by_col: dict[str, list[dict]] = {}
        for collection in collections:
            try:
                response = await self._client.post(
                    f"{self._base_url}/collections/{collection}/points/search",
                    json={
                        "vector": query_vector,
                        "limit": PER_COL,
                        "with_payload": True,
                        "score_threshold": min_relevance,
                    },
                )
                response.raise_for_status()
                points = response.json().get("result", []) or []
                results_by_col[collection] = [
                    {
                        "type": p.get("payload", {}).get("type", collection),
                        "filename": p.get("payload", {}).get("filename", ""),
                        "page": p.get("payload", {}).get("page"),
                        "date": p.get("payload", {}).get("date"),
                        "uploader": p.get("payload", {}).get("uploader"),
                        "excerpt": p.get("payload", {}).get("text", ""),
                        "relevance_score": p.get("score", 0.0),
                    }
                    for p in points
                ]
            except Exception as exc:
                logger.warning("qdrant_search_failed", collection=collection, error=str(exc))
                results_by_col[collection] = []

        # Round-robin merge: rank-1 from each col, then rank-2 from each, ...
        # Deduplicate by (filename, page, excerpt[:160]).
        seen: set[tuple[str, int | None, str]] = set()
        merged: list[dict] = []
        for rank in range(PER_COL):
            for col in collections:
                if rank >= len(results_by_col.get(col, [])):
                    continue
                r = results_by_col[col][rank]
                key = (r["filename"], r.get("page"), (r.get("excerpt") or "")[:160])
                if key in seen:
                    continue
                seen.add(key)
                merged.append(r)
                if len(merged) >= top_k:
                    return merged
        return merged

    async def close(self) -> None:
        await self._client.aclose()
