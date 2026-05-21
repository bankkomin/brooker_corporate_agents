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
        top_k: int = 8,
        min_relevance: float = 0.70,
    ) -> list[dict]:
        """Search across multiple Qdrant collections, merge and deduplicate results."""
        all_results: list[dict] = []
        for collection in collections:
            try:
                response = await self._client.post(
                    f"{self._base_url}/collections/{collection}/points/search",
                    json={
                        "vector": query_vector,
                        "limit": top_k,
                        "with_payload": True,
                        "score_threshold": min_relevance,
                    },
                )
                response.raise_for_status()
                data = response.json()
                for point in data.get("result", []):
                    payload = point.get("payload", {})
                    all_results.append(
                        {
                            "type": payload.get("type", collection),
                            "filename": payload.get("filename", ""),
                            "page": payload.get("page"),
                            "date": payload.get("date"),
                            "uploader": payload.get("uploader"),
                            "excerpt": payload.get("text", ""),
                            "relevance_score": point.get("score", 0.0),
                        }
                    )
            except Exception as exc:
                logger.warning("qdrant_search_failed", collection=collection, error=str(exc))

        # Deduplicate by (filename, page, excerpt) and sort by relevance.
        # NOTE: keying on (filename, page) alone collapsed every multi-chunk
        # document to ONE chunk — vault/wiki docs are chunked with page=None,
        # so an entire retreat note surfaced as a single fragment. Including the
        # excerpt keeps distinct chunks of the same file while removing true dups.
        seen: set[tuple[str, int | None, str]] = set()
        deduped: list[dict] = []
        for r in sorted(all_results, key=lambda x: x["relevance_score"], reverse=True):
            key = (r["filename"], r.get("page"), (r.get("excerpt") or "")[:160])
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        return deduped[:top_k]

    async def close(self) -> None:
        await self._client.aclose()
