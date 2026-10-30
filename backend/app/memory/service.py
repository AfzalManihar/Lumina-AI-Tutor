"""Long-term memory: explicit, consented, user-owned, relevance-retrieved. Memories are never written
from model output or document content - only from direct, authenticated user actions."""
from __future__ import annotations

import re
from typing import Any

from bson import ObjectId

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.security import utcnow
from app.guardrails.retrieval import validate_object_id
from app.rag.embeddings import tokenize

SENSITIVE = re.compile(
    r"(password|passwd|passcode|api[_ -]?key|secret|token|otp|cvv|card number|\b\d{13,19}\b|"
    r"private key|aadhaar|ssn|bearer\s+\S+)", re.I)

SOURCES = ("user_manual", "approved_suggestion")


def mem_out(m: dict) -> dict:
    return {"id": str(m["_id"]), "text": m["text"], "type": m["type"], "source": m["source"],
            "conversation_id": m.get("conversation_id"), "created_at": m["created_at"],
            "updated_at": m["updated_at"]}


def reject_sensitive(text: str) -> None:
    if SENSITIVE.search(text):
        raise AppError("Memories must not contain passwords, keys, payment or other sensitive data",
                       code="sensitive_content", status_code=422)


def suggest_memory_from_message(message: str) -> dict | None:
    """Deterministically propose (never save) a memory when the user states a preference/goal."""
    m = re.match(r"^\s*(?:please\s+)?remember (?:that\s+)?(.{3,300})$", message, re.I | re.S)
    if m:
        text, typ = m.group(1).strip().rstrip("."), "fact"
    else:
        g = re.search(r"\bmy (?:learning )?goal is (?:to )?(.{3,200})", message, re.I)
        p = re.search(r"\bi (?:prefer|like|learn best with) (.{3,200})", message, re.I)
        if g:
            text, typ = "Goal: " + g.group(1).strip().rstrip("."), "goal"
        elif p:
            text, typ = "Prefers " + p.group(1).strip().rstrip("."), "preference"
        else:
            return None
    if SENSITIVE.search(text):
        return None
    if re.match(r"(?i)(goal|prefers)", text):
        pass
    elif re.search(r"\bprefer|like to|learn best", text, re.I):
        typ = "preference"
    return {"text": text[:500], "type": typ}


class MemoryService:
    def __init__(self, db: Any, settings: Settings):
        self.db, self.s = db, settings

    async def enabled_for(self, user: dict) -> bool:
        return bool(self.s.memory_enabled and user.get("settings", {}).get("memory_enabled", True))

    async def create(self, user: dict, text: str, mtype: str, source: str, conversation_id: str | None = None) -> dict:
        if not await self.enabled_for(user):
            raise ForbiddenError("Memory is disabled for this account", code="memory_disabled")
        if source not in SOURCES:
            raise AppError("Invalid memory source", code="invalid_source", status_code=422)
        reject_sensitive(text)
        doc = {"user_id": str(user["_id"]), "text": text.strip(), "type": mtype, "source": source,
               "conversation_id": conversation_id, "created_at": utcnow(), "updated_at": utcnow()}
        res = await self.db.memories.insert_one(doc)
        doc["_id"] = res.inserted_id
        return mem_out(doc)

    async def _owned(self, user_id: str, mem_id: str) -> dict:
        validate_object_id(mem_id, "memory id")
        m = await self.db.memories.find_one({"_id": ObjectId(mem_id), "user_id": user_id})
        if not m:
            raise NotFoundError("Memory not found")
        return m

    async def list(self, user_id: str, limit: int, skip: int) -> dict:
        total = await self.db.memories.count_documents({"user_id": user_id})
        rows = await self.db.memories.find({"user_id": user_id}).sort("updated_at", -1).skip(skip).to_list(limit)
        return {"items": [mem_out(m) for m in rows], "total": total}

    async def update(self, user: dict, mem_id: str, text: str | None, mtype: str | None) -> dict:
        m = await self._owned(str(user["_id"]), mem_id)
        sets: dict = {"updated_at": utcnow()}
        if text is not None:
            reject_sensitive(text)
            sets["text"] = text.strip()
        if mtype is not None:
            sets["type"] = mtype
        await self.db.memories.update_one({"_id": m["_id"], "user_id": str(user["_id"])}, {"$set": sets})
        return mem_out(await self.db.memories.find_one({"_id": m["_id"]}))

    async def delete(self, user_id: str, mem_id: str) -> None:
        m = await self._owned(user_id, mem_id)
        await self.db.memories.delete_one({"_id": m["_id"], "user_id": user_id})

    async def delete_all(self, user_id: str) -> int:
        return (await self.db.memories.delete_many({"user_id": user_id})).deleted_count

    async def relevant(self, user: dict, query: str, limit: int | None = None) -> list[dict]:
        """Only memories with real lexical relevance to the query (plus goals) are returned."""
        if not await self.enabled_for(user):
            return []
        limit = limit or self.s.memory_retrieval_limit
        q = set(tokenize(query))
        rows = await self.db.memories.find({"user_id": str(user["_id"])}).to_list(500)
        scored = []
        for m in rows:
            t = set(tokenize(m["text"]))
            overlap = len(q & t) / (len(q | t) or 1)
            boost = 0.05 if m["type"] in ("goal", "preference") else 0.0
            if overlap > 0 or (boost and m["type"] == "preference"):
                scored.append((overlap + boost, m))
        scored.sort(key=lambda x: (x[0], x[1]["updated_at"]), reverse=True)
        return [mem_out(m) for _, m in scored[:limit]]
