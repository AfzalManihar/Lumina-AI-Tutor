"""Builds provider-backed components from app state, honouring test overrides."""
from __future__ import annotations

from typing import Any

from fastapi import Request

from app.rag.embeddings import get_embedder
from app.rag.retriever import Retriever
from app.rag.store import get_vector_store


def get_embedder_for(request: Request):
    return request.app.state.embedder_override or get_embedder(request.app.state.settings)


def get_retriever_for(request: Request) -> Retriever:
    s, db = request.app.state.settings, request.app.state.db
    emb = get_embedder_for(request)
    return Retriever(db, s, emb, get_vector_store(s, db))


def get_llm_for(request: Request):
    if request.app.state.llm_override is not None:
        return request.app.state.llm_override
    from app.agents.llm import LLMClient
    return LLMClient(request.app.state.settings)


class LazyRetriever:
    """Defers embedder/vector-store construction so plain chat works without RAG configuration.
    A configuration error surfaces only when retrieval is actually attempted (never silently skipped)."""

    def __init__(self, app: Any):
        self._app = app
        self._inst: Retriever | None = None

    def _get(self) -> Retriever:
        if self._inst is None:
            s, db = self._app.state.settings, self._app.state.db
            emb = self._app.state.embedder_override or get_embedder(s)
            self._inst = Retriever(db, s, emb, get_vector_store(s, db))
        return self._inst

    async def retrieve(self, *args, **kwargs):
        return await self._get().retrieve(*args, **kwargs)


def get_lazy_retriever(request: Request) -> LazyRetriever:
    return LazyRetriever(request.app)
