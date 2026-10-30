"""MongoDB access (PyMongo native async client) and index management."""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings

log = logging.getLogger("lumina.db")

COLLECTIONS = ("users", "sessions", "login_attempts", "conversations", "messages", "documents",
               "chunks", "memories", "learning_events", "subscriptions", "payments",
               "webhook_events", "usage", "audit_events", "quizzes", "lessons")


def create_client(settings: Settings) -> Any:
    from pymongo import AsyncMongoClient
    return AsyncMongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000, tz_aware=True)


async def ensure_indexes(db: Any) -> None:
    await db.users.create_index("email", unique=True)
    await db.sessions.create_index("refresh_hash", unique=True)
    await db.sessions.create_index("prev_hashes")
    await db.sessions.create_index([("user_id", 1), ("revoked", 1)])
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("key", unique=True)
    await db.login_attempts.create_index("expires_at", expireAfterSeconds=0)
    await db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.messages.create_index("user_id")
    await db.documents.create_index([("user_id", 1), ("created_at", -1)])
    await db.chunks.create_index([("user_id", 1), ("document_id", 1)])
    await db.memories.create_index([("user_id", 1), ("updated_at", -1)])
    await db.learning_events.create_index([("user_id", 1), ("created_at", -1)])
    await db.quizzes.create_index([("user_id", 1), ("created_at", -1)])
    await db.lessons.create_index([("user_id", 1), ("created_at", -1)])
    await db.subscriptions.create_index([("user_id", 1), ("status", 1)])
    await db.payments.create_index("razorpay_order_id", unique=True)
    await db.payments.create_index([("user_id", 1), ("created_at", -1)])
    await db.webhook_events.create_index("event_key", unique=True)
    await db.usage.create_index([("user_id", 1), ("period", 1)], unique=True)
    await db.audit_events.create_index([("user_id", 1), ("created_at", -1)])
    await db.traces.create_index("created_at", expireAfterSeconds=30 * 24 * 3600)  # trace metadata is kept 30 days


async def ping(db: Any) -> bool:
    try:
        await db.command("ping")
        return True
    except Exception:  # noqa: BLE001
        return False
