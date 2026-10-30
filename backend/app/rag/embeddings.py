"""Embedding providers. 'google' calls the Gemini embedding REST API; 'hash' is a deterministic local
feature-hashing embedder (lexical, NOT semantic) intended for offline development and tests only."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

from app.core.config import Settings
from app.core.errors import ConfigError, ProviderError

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an the of and or to in on for with is are was were be by as at it this that from".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


def stem(t: str) -> str:
    """Very light suffix stripping so 'melt'/'melts'/'melting' share a feature in the lexical embedder."""
    for suf in ("ations", "ation", "ings", "ing", "ies", "es", "ed", "s"):
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


class Embedder(Protocol):
    name: str
    dim: int | None
    semantic: bool

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    name = "hash"
    semantic = False

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        toks = [stem(x) for x in tokenize(text)]
        feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    async def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    async def embed_query(self, text):
        return self._vec(text)


class GoogleEmbedder:
    name = "google"
    semantic = True
    dim = None

    def __init__(self, settings: Settings):
        if not settings.google_api_key:
            raise ConfigError("GOOGLE_API_KEY is required for EMBEDDING_PROVIDER=google")
        self.s = settings
        self.model = settings.google_embedding_model
        self.base = "https://generativelanguage.googleapis.com/v1beta"

    async def _post(self, path: str, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(f"{self.base}/{path}", json=payload, headers={"x-goog-api-key": self.s.google_api_key})
        except httpx.HTTPError:
            raise ProviderError("Embedding provider unreachable")
        if r.status_code >= 400:
            raise ProviderError(f"Embedding provider error (HTTP {r.status_code})")
        return r.json()

    async def embed_documents(self, texts):
        out: list[list[float]] = []
        for i in range(0, len(texts), 50):
            batch = texts[i:i + 50]
            data = await self._post(f"{self.model}:batchEmbedContents", {"requests": [
                {"model": self.model, "content": {"parts": [{"text": t}]}, "taskType": "RETRIEVAL_DOCUMENT"}
                for t in batch]})
            embs = data.get("embeddings", [])
            if len(embs) != len(batch):
                raise ProviderError("Embedding provider returned an unexpected number of vectors")
            out.extend(e["values"] for e in embs)
        return out

    async def embed_query(self, text):
        data = await self._post(f"{self.model}:embedContent", {
            "model": self.model, "content": {"parts": [{"text": text}]}, "taskType": "RETRIEVAL_QUERY"})
        return data["embedding"]["values"]


def get_embedder(settings: Settings) -> Embedder:
    p = settings.embedding_provider
    if p == "hash":
        return HashEmbedder()
    if p == "google":
        return GoogleEmbedder(settings)
    raise ConfigError("EMBEDDING_PROVIDER is not configured (set to 'google' or, for offline dev only, 'hash')")
