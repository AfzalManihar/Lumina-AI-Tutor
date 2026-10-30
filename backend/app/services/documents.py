
"""Document lifecycle: upload, extract, chunk, embed, store, and reindex."""
from __future__ import annotations

import math
from typing import Any

from bson import ObjectId

from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.guardrails.retrieval import validate_object_id
from app.models.enums import DOC_FAILED, DOC_PROCESSING, DOC_READY
from app.rag.embeddings import Embedder
from app.rag.ingest import chunk_pages, extract_pages, validate_upload
from app.rag.store import VectorStore
from app.services.plans import get_plans
from app.services.usage import effective_plan_id


def doc_out(document: dict) -> dict:
    """Return the public document representation."""
    return {
        "id": str(document["_id"]),
        "filename": document["filename"],
        "kind": document["kind"],
        "size_bytes": document["size_bytes"],
        "status": document["status"],
        "pages": document.get("pages"),
        "chunk_count": document.get("chunk_count", 0),
        "error": document.get("error"),
        "embedding_provider": document.get("embedding_provider"),
        "created_at": document["created_at"],
    }


def _validate_vectors(vectors: list, expected_count: int) -> int:
    """Reject incomplete, inconsistent, empty, or invalid embedding batches."""
    if len(vectors) != expected_count:
        raise AppError(
            "Embedding provider returned an incomplete vector batch",
            code="embedding_count_mismatch",
            status_code=502,
        )

    if expected_count == 0:
        return 0

    dimension: int | None = None

    for index, vector in enumerate(vectors):
        if not isinstance(vector, (list, tuple)) or not vector:
            raise AppError(
                f"Embedding provider returned an empty vector at position {index}",
                code="invalid_embedding",
                status_code=502,
            )

        if dimension is None:
            dimension = len(vector)
        elif len(vector) != dimension:
            raise AppError(
                "Embedding provider returned vectors with inconsistent dimensions",
                code="embedding_dimension_mismatch",
                status_code=502,
            )

        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError, OverflowError) as exc:
            raise AppError(
                "Embedding provider returned non-numeric vector values",
                code="invalid_embedding",
                status_code=502,
            ) from exc

        if not all(math.isfinite(value) for value in values):
            raise AppError(
                "Embedding provider returned non-finite vector values",
                code="invalid_embedding",
                status_code=502,
            )

        if not any(value != 0.0 for value in values):
            raise AppError(
                "Embedding provider returned a zero vector",
                code="invalid_embedding",
                status_code=502,
            )

    return dimension or 0


class DocumentService:
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

    async def upload(
        self,
        user_id: str,
        filename: str,
        mime: str | None,
        data: bytes,
    ) -> dict:
        safe_name = (
            (filename or "document")
            .replace("\\", "/")
            .rsplit("/", 1)[-1][:150]
            or "document"
        )

        kind = validate_upload(data, safe_name, mime, self.s)
        plan_id = await effective_plan_id(self.db, user_id)
        plan = get_plans(self.s)[plan_id]

        count = await self.db.documents.count_documents(
            {"user_id": user_id}
        )
        if count >= plan.max_documents:
            raise AppError(
                f"Document limit reached for the {plan.name} plan "
                f"({plan.max_documents})",
                code="document_limit",
                status_code=402,
            )

        pages = extract_pages(data, kind, self.s)
        chunks = chunk_pages(pages, self.s)

        if not chunks:
            raise AppError(
                "No extractable text was found in this document",
                code="empty_document",
                status_code=422,
            )

        now = utcnow()
        document = {
            "user_id": user_id,
            "filename": safe_name,
            "kind": kind,
            "size_bytes": len(data),
            "status": DOC_PROCESSING,
            "pages": len(pages),
            "chunk_count": 0,
            "embedding_provider": self.embedder.name,
            "created_at": now,
            "updated_at": now,
        }

        result = await self.db.documents.insert_one(document)
        document_id = str(result.inserted_id)

        try:
            await self._index(user_id, document_id, chunks)

            await self.db.documents.update_one(
                {"_id": result.inserted_id, "user_id": user_id},
                {
                    "$set": {
                        "status": DOC_READY,
                        "chunk_count": len(chunks),
                        "embedding_provider": self.embedder.name,
                        "error": None,
                        "updated_at": utcnow(),
                    }
                },
            )
        except Exception as exc:
            # Clean up chunks if indexing fails.
            await self.store.delete_document(user_id, document_id)
            await self.db.documents.update_one(
                {"_id": result.inserted_id, "user_id": user_id},
                {
                    "$set": {
                        "status": DOC_FAILED,
                        "error": f"Indexing failed: {type(exc).__name__}",
                        "updated_at": utcnow(),
                    }
                },
            )
            raise

        saved = await self.db.documents.find_one(
            {"_id": result.inserted_id, "user_id": user_id}
        )
        return doc_out(saved)

    async def _index(
        self,
        user_id: str,
        document_id: str,
        chunks,
    ) -> None:
        """Generate and store validated chunk embeddings."""
        texts = [chunk.text for chunk in chunks]
        vectors = await self.embedder.embed_documents(texts)
        dimension = _validate_vectors(vectors, len(chunks))

        now = utcnow()
        rows = [
            {
                "index": chunk.index,
                "text": chunk.text,
                "page": chunk.page,
                "section": chunk.section,
                "embedding": [float(value) for value in vector],
                "embedding_provider": self.embedder.name,
                "embedding_dimension": dimension,
                "created_at": now,
            }
            for chunk, vector in zip(chunks, vectors)
        ]

        await self.store.add(user_id, document_id, rows)

    async def _owned(
        self,
        user_id: str,
        document_id: str,
    ) -> dict:
        """Return a document only when it belongs to the requesting user."""
        validate_object_id(document_id, "document id")

        document = await self.db.documents.find_one(
            {
                "_id": ObjectId(document_id),
                "user_id": user_id,
            }
        )
        if not document:
            raise NotFoundError("Document not found")

        return document

    async def list(
        self,
        user_id: str,
        limit: int,
        skip: int,
    ) -> dict:
        total = await self.db.documents.count_documents(
            {"user_id": user_id}
        )

        documents = (
            await self.db.documents.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(skip)
            .to_list(limit)
        )

        return {
            "items": [doc_out(document) for document in documents],
            "total": total,
        }

    async def get(
        self,
        user_id: str,
        document_id: str,
    ) -> dict:
        document = await self._owned(user_id, document_id)
        return doc_out(document)

    async def delete(
        self,
        user_id: str,
        document_id: str,
    ) -> None:
        document = await self._owned(user_id, document_id)

        await self.store.delete_document(user_id, document_id)
        await self.db.documents.delete_one(
            {
                "_id": document["_id"],
                "user_id": user_id,
            }
        )

        await self.db.audit_events.insert_one(
            {
                "user_id": user_id,
                "type": "document_deleted",
                "created_at": utcnow(),
            }
        )

    async def reindex(
        self,
        user_id: str,
        document_id: str,
    ) -> dict:
        """Re-embed all passages and validate vectors before updating chunks."""
        document = await self._owned(user_id, document_id)

        old_chunks = (
            await self.db.chunks.find(
                {
                    "user_id": user_id,
                    "document_id": document_id,
                }
            )
            .sort("index", 1)
            .to_list(100000)
        )

        if not old_chunks:
            raise AppError(
                "Nothing to re-index",
                code="empty_document",
                status_code=422,
            )

        # Validate the complete embedding batch before changing any stored vector.
        vectors = await self.embedder.embed_documents(
            [chunk["text"] for chunk in old_chunks]
        )
        dimension = _validate_vectors(vectors, len(old_chunks))

        now = utcnow()

        # update_one is compatible with MongoDB and mongomock.
        # It avoids the bulk_write incompatibility seen in the test suite.
        for chunk, vector in zip(old_chunks, vectors):
            result = await self.db.chunks.update_one(
                {
                    "_id": chunk["_id"],
                    "user_id": user_id,
                    "document_id": document_id,
                },
                {
                    "$set": {
                        "embedding": [float(value) for value in vector],
                        "embedding_provider": self.embedder.name,
                        "embedding_dimension": dimension,
                        "updated_at": now,
                    }
                },
            )

            if result.matched_count != 1:
                raise AppError(
                    "Reindex could not update every passage; retry reindexing",
                    code="reindex_incomplete",
                    status_code=500,
                )

        await self.db.documents.update_one(
            {
                "_id": document["_id"],
                "user_id": user_id,
            },
            {
                "$set": {
                    "embedding_provider": self.embedder.name,
                    "embedding_dimension": dimension,
                    "chunk_count": len(old_chunks),
                    "status": DOC_READY,
                    "error": None,
                    "updated_at": now,
                }
            },
        )

        updated = await self.db.documents.find_one(
            {
                "_id": document["_id"],
                "user_id": user_id,
            }
        )
        return doc_out(updated)

    async def passages(
        self,
        user_id: str,
        document_id: str,
        page: int | None,
        limit: int = 10,
    ) -> list[dict]:
        """Return stored passages after checking document ownership."""
        await self._owned(user_id, document_id)

        query_filter: dict = {
            "user_id": user_id,
            "document_id": document_id,
        }
        if page is not None:
            query_filter["page"] = page

        rows = (
            await self.db.chunks.find(query_filter)
            .sort("index", 1)
            .to_list(limit)
        )

        return [
            {
                "chunk_id": str(row["_id"]),
                "page": row.get("page"),
                "section": row.get("section"),
                "text": row["text"],
            }
            for row in rows
        ]
