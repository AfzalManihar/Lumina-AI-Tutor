"""Rate limiting: DB-backed brute-force protection and an in-process API limiter."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Any

from app.core.config import Settings
from app.core.errors import RateLimitError
from app.core.security import utcnow


class LoginThrottle:
    """Counts failed attempts per key (email+ip) in MongoDB with TTL expiry."""

    def __init__(self, db: Any, settings: Settings):
        self.db, self.s = db, settings

    async def check(self, key: str) -> None:
        doc = await self.db.login_attempts.find_one({"key": key})
        if doc and doc["count"] >= self.s.auth_rate_limit_attempts and doc["expires_at"] > utcnow():
            retry = max(1, int((doc["expires_at"] - utcnow()).total_seconds()))
            raise RateLimitError("Too many failed attempts. Try again later.",
                                 details={"retry_after": retry})

    async def record_failure(self, key: str) -> None:
        exp = utcnow() + timedelta(seconds=self.s.auth_rate_limit_window_seconds)
        await self.db.login_attempts.update_one(
            {"key": key}, {"$inc": {"count": 1}, "$set": {"expires_at": exp}}, upsert=True)

    async def reset(self, key: str) -> None:
        await self.db.login_attempts.delete_one({"key": key})


class SlidingWindowLimiter:
    """Simple per-process sliding window limiter. Use a shared store (Redis) for multi-instance deployments."""

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit, self.window = limit, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise RateLimitError("Rate limit exceeded", details={"retry_after": int(self.window - (now - q[0])) + 1})
        q.append(now)
