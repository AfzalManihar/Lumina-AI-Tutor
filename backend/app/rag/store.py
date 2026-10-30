
"""MongoDB vector store with safe cosine similarity and dimension diagnostics."""
from __future__ import annotations

import logging
import math
from typing import Any, Protocol

logger = logging.getLogger(__name__)


def cosine(a: list[float], b: list[float]) -> float:
    """Return cosine similarity; invalid vectors never produce NaN or infinity."""
    if not a or not b:
        return 0.0

    if len(a) != len(b):
        logger.warning(
            "RAG embedding dimension mismatch: query_dim=%d stored_dim=%d",
            len(a),
            len(b),
        )
        return 0.0

    try:
        if not all(math.isfinite(float(x)) for x in a):
            return 0.0
        if not all(math.isfinite(float(y)) for y in b):
            return 0.0

        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        norm_a = math.sqrt(sum(float(x) ** 2 for x in a))
        norm_b = math.sqrt(sum(float(y) ** 2 for y in b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        score = dot / (norm_a * norm_b)
        return max(-1.0, min(1.0, score)) if math.isfinite(score) else 0.0
    except (TypeError, ValueError, OverflowError):
        logger.warning("RAG encountered an invalid embedding vector")
        return 0.0


class VectorStore(Protocol):
    async def add(
        self, user_id: str, document_id: str, chunks: list[dict]
    ) -> None: ...

    async def search(
        self,
        user_id: str,
        query_vec: list[float],
        top_k: int,
        document_ids: list[str] | None,
    ) -> list[dict]: ...

    async def delete_document(self, user_id: str, document_id: str) -> int: ...


class MongoVectorStore:
    def __init__(self, db: Any):
        self.db = db

    async def add(self, user_id: str, document_id: str, chunks: list[dict]) -> None:
        if not chunks:
            return

        rows = [
            {
                **chunk,
                "user_id": user_id,
                "document_id": document_id,
            }
            for chunk in chunks
        ]
        await self.db.chunks.insert_many(rows)

    async def search(
        self,
        user_id: str,
        query_vec: list[float],
        top_k: int,
        document_ids: list[str] | None,
    ) -> list[dict]:
        # Enforce ownership and optional document scope in MongoDB before scoring.
        query_filter: dict = {"user_id": user_id}

        if document_ids is not None:
            query_filter["document_id"] = {"$in": list(document_ids)}

        scored: list[tuple[float, dict]] = []

        async for chunk in self.db.chunks.find(query_filter):
            embedding = chunk.get("embedding")

            if not isinstance(embedding, list):
                logger.warning(
                    "RAG chunk has missing or invalid embedding: chunk_id=%s",
                    str(chunk.get("_id", "")),
                )
                continue

            score = cosine(query_vec, embedding)
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {**chunk, "score": score}
            for score, chunk in scored[:max(1, top_k)]
        ]

    async def delete_document(self, user_id: str, document_id: str) -> int:
        result = await self.db.chunks.delete_many(
            {"user_id": user_id, "document_id": document_id}
        )
        return result.deleted_count


def get_vector_store(settings, db) -> VectorStore:
    if settings.vector_store_provider == "mongo":
        return MongoVectorStore(db)

    from app.core.errors import ConfigError

    raise ConfigError(
        "VECTOR_STORE_PROVIDER is not configured (set to 'mongo')"
    )
