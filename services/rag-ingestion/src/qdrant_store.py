"""Async Qdrant client wrapper for vector CRUD operations."""
from __future__ import annotations

import uuid

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from .config import RAGSettings

logger = structlog.get_logger("rag-ingestion.qdrant_store")

COLLECTIONS = ["cac_docs", "cac_chat", "cac_knowledge", "shared_policies"]


class QdrantStore:
    """Async wrapper for Qdrant vector operations."""

    def __init__(self, settings: RAGSettings) -> None:
        self._client = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_rest_port,
        )

    async def ensure_collections(self, vector_size: int) -> None:
        """Create collections if they don't exist."""
        existing = await self._client.get_collections()
        existing_names = {c.name for c in existing.collections}
        for name in COLLECTIONS:
            if name not in existing_names:
                await self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                logger.info("qdrant_store.collection_created", name=name, dim=vector_size)

    async def upsert_chunks(
        self,
        collection: str,
        texts: list[str],
        vectors: list[list[float]],
        metadatas: list[dict],
    ) -> int:
        """Batch upsert text chunks with vectors and metadata."""
        points = []
        for text, vec, meta in zip(texts, vectors, metadatas, strict=True):
            point_id = str(uuid.uuid4())
            payload = {**meta, "text": text}
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))

        if points:
            await self._client.upsert(collection_name=collection, points=points)
            logger.info("qdrant_store.upserted", collection=collection, count=len(points))
        return len(points)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 8,
        score_threshold: float = 0.70,
        filters: dict[str, str] | None = None,
    ) -> list[dict]:
        """Search for similar vectors with optional metadata filters."""
        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=qdrant_filter,
        )
        return [
            {
                "text": hit.payload.get("text", "") if hit.payload else "",
                "score": hit.score,
                "id": str(hit.id),
                **(hit.payload or {}),
            }
            for hit in results
        ]

    async def delete_by_file(self, collection: str, file_path: str) -> None:
        """Delete all points matching a source file."""
        await self._client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[FieldCondition(key="source_file", match=MatchValue(value=file_path))]
            ),
        )
        logger.info("qdrant_store.deleted_by_file", collection=collection, file=file_path)

    async def get_collection_info(self, collection: str) -> dict:
        """Get collection stats."""
        info = await self._client.get_collection(collection)
        return {
            "name": collection,
            "vectors_count": info.vectors_count or 0,
            "status": str(info.status),
        }

    async def health_check(self) -> bool:
        """Check Qdrant connectivity."""
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.close()
