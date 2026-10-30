
"""Authorized retrieval with automatic embedding-dimension migration."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

from bson import ObjectId

from app.core.config import Settings
from app.guardrails.retrieval import validate_object_id
from app.rag.embeddings import Embedder
from app.rag.store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    status: str  # ok | no_documents | no_relevant_results
    hits: list[dict] = field(default_factory=list)
    searched_documents: int = 0


def public_hit(h: dict) -> dict:
    return {
        "cite_id": h["cite_id"],
        "chunk_id": h["chunk_id"],
        "document_id": h["document_id"],
        "filename": h.get("filename", ""),
        "page": h.get("page"),
        "section": h.get("section"),
        "text": h["text"],
        "score": round(float(h["score"]), 4),
    }


class Retriever:
    def __init__(
        self,
        db: Any,
        settings: Settings,
        embedder: Embedder,
        store: VectorStore,
    ):
        self.db = db
        self.s = settings
        self.embedder = embedder
        self.store = store

    async def authorized_document_ids(
        self,
        user_id: str,
        requested: list[str] | None,
    ) -> list[str]:
        """Return only ready documents owned by this user."""
        document_filter: dict = {
            "user_id": user_id,
            "status": "ready",
        }

        if requested is not None:
            ids = [
                ObjectId(validate_object_id(doc_id, "document id"))
                for doc_id in requested
            ]
            document_filter["_id"] = {"$in": ids}

        documents = await self.db.documents.find(
            document_filter
        ).to_list(1000)

        return [str(document["_id"]) for document in documents]

    async def _ensure_embedding_dimensions(
        self,
        user_id: str,
        document_ids: list[str],
        query_dimension: int,
    ) -> None:
        """
        Automatically migrate authorized document chunks when their stored
        embedding dimensions differ from the active query embedder.
        """
        chunks = await self.db.chunks.find(
            {
                "user_id": user_id,
                "document_id": {"$in": document_ids},
            }
        ).to_list(100000)

        if not chunks:
            return

        def dimension(chunk: dict) -> int:
            vector = chunk.get("embedding")
            return len(vector) if isinstance(vector, list) else -1

        needs_migration = any(
            dimension(chunk) != query_dimension
            for chunk in chunks
        )

        if not needs_migration:
            return

        logger.warning(
            "RAG embedding migration started: documents=%d chunks=%d target_dim=%d",
            len(document_ids),
            len(chunks),
            query_dimension,
        )

        # Prepare and validate every vector before modifying stored chunks.
        texts = [str(chunk.get("text") or "") for chunk in chunks]
        if any(not text.strip() for text in texts):
            raise RuntimeError(
                "Cannot reindex document chunks: one or more chunks have empty text."
            )

        vectors = await self.embedder.embed_documents(texts)

        if len(vectors) != len(chunks):
            raise RuntimeError(
                "Embedding migration failed: provider returned an unexpected "
                "number of vectors. Existing chunks were not updated."
            )

        for vector in vectors:
            if (
                not isinstance(vector, list)
                or len(vector) != query_dimension
                or not vector
                or not all(
                    isinstance(value, (int, float))
                    and math.isfinite(value)
                    for value in vector
                )
                or not any(value != 0 for value in vector)
            ):
                raise RuntimeError(
                    "Embedding migration failed: generated vectors are invalid "
                    "or do not match the active query embedding dimension. "
                    "Existing chunks were not updated."
                )

        # Only write after all vectors have passed validation.
        for chunk, vector in zip(chunks, vectors):
            result = await self.db.chunks.update_one(
                {
                    "_id": chunk["_id"],
                    "user_id": user_id,
                    "document_id": chunk["document_id"],
                },
                {
                    "$set": {
                        "embedding": vector,
                        "embedding_provider": self.embedder.name,
                        "embedding_dimension": query_dimension,
                    }
                },
            )

            if getattr(result, "matched_count", 1) != 1:
                raise RuntimeError(
                    "Embedding migration stopped because a chunk changed "
                    "or was no longer accessible."
                )

        # Keep document-level embedding metadata consistent with its chunks.
        for document_id in document_ids:
            await self.db.documents.update_one(
                {
                    "_id": ObjectId(document_id),
                    "user_id": user_id,
                },
                {
                    "$set": {
                        "embedding_provider": self.embedder.name,
                        "embedding_dimension": query_dimension,
                    }
                },
            )

        logger.warning(
            "RAG embedding migration completed: chunks=%d dimension=%d provider=%s",
            len(chunks),
            query_dimension,
            self.embedder.name,
        )

    async def retrieve(
        self,
        user_id: str,
        query: str,
        document_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        allowed_ids = await self.authorized_document_ids(
            user_id, document_ids
        )

        if not allowed_ids:
            logger.warning(
                "RAG: no ready documents found for user; requested_document_count=%d",
                len(document_ids) if document_ids is not None else 0,
            )
            return RetrievalResult("no_documents", [], 0)

        query_vector = await self.embedder.embed_query(query)

        if not query_vector:
            raise RuntimeError(
                "The embedding provider returned an empty query vector."
            )

        # Repair legacy chunks before similarity search, then search again
        # using the newly consistent embeddings.
        await self._ensure_embedding_dimensions(
            user_id=user_id,
            document_ids=allowed_ids,
            query_dimension=len(query_vector),
        )

        raw_hits = await self.store.search(
            user_id,
            query_vector,
            top_k or self.s.rag_top_k,
            allowed_ids,
        )

        logger.warning(
            "RAG: allowed_docs=%d raw_chunks=%d min_score=%s scores=%s",
            len(allowed_ids),
            len(raw_hits),
            self.s.rag_min_score,
            [
                round(float(hit.get("score", 0.0)), 4)
                for hit in raw_hits
            ],
        )

        filtered_hits = [
            hit
            for hit in raw_hits
            if float(hit.get("score", 0.0)) >= self.s.rag_min_score
        ]

        if not filtered_hits:
            return RetrievalResult(
                "no_relevant_results",
                [],
                len(allowed_ids),
            )

        documents = await self.db.documents.find(
            {
                "user_id": user_id,
                "_id": {
                    "$in": [ObjectId(doc_id) for doc_id in allowed_ids]
                },
            }
        ).to_list(1000)

        filenames = {
            str(document["_id"]): document.get("filename", "")
            for document in documents
        }

        hits = []
        for index, hit in enumerate(filtered_hits, start=1):
            document_id = str(hit["document_id"])

            hits.append(
                {
                    "cite_id": f"S{index}",
                    "chunk_id": str(hit["_id"]),
                    "document_id": document_id,
                    "filename": filenames.get(document_id, ""),
                    "page": hit.get("page"),
                    "section": hit.get("section"),
                    "text": hit["text"],
                    "score": float(hit["score"]),
                }
            )

        return RetrievalResult("ok", hits, len(allowed_ids))
