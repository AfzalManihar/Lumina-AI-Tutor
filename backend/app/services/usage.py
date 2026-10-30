"""Monthly token usage with atomic reservation so concurrent requests cannot exceed the allowance."""
from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.errors import UsageLimitError
from app.core.security import utcnow
from app.models.enums import PLAN_FREE
from app.services.plans import get_plans


def current_period() -> str:
    n = utcnow()
    return f"{n.year:04d}-{n.month:02d}"


async def effective_plan_id(db: Any, user_id: str) -> str:
    """Plan is derived from a verified, active, unexpired subscription - never from client input."""
    sub = await db.subscriptions.find_one(
        {"user_id": user_id, "status": "active", "expires_at": {"$gt": utcnow()}},
        sort=[("expires_at", -1)])
    return sub["plan_id"] if sub else PLAN_FREE


async def monthly_limit(db: Any, settings: Settings, user_id: str) -> int:
    plans = get_plans(settings)
    pid = await effective_plan_id(db, user_id)
    return plans.get(pid, plans[PLAN_FREE]).monthly_token_limit


class UsageService:
    def __init__(self, db: Any, settings: Settings):
        self.db, self.s = db, settings

    async def _ensure(self, user_id: str, period: str) -> None:
        await self.db.usage.update_one(
            {"user_id": user_id, "period": period},
            {"$setOnInsert": {"tokens_used": 0, "requests": 0, "by_feature": {}, "created_at": utcnow()}},
            upsert=True)

    async def reserve(self, user_id: str, tokens: int) -> dict:
        """Atomically add `tokens` to usage only if it stays within the limit."""
        period = current_period()
        limit = await monthly_limit(self.db, self.s, user_id)
        await self._ensure(user_id, period)
        doc = await self.db.usage.find_one_and_update(
            {"user_id": user_id, "period": period, "tokens_used": {"$lte": limit - tokens}},
            {"$inc": {"tokens_used": tokens, "requests": 1}},
            return_document=True)
        if doc is None:
            raise UsageLimitError("Monthly token allowance exhausted. Upgrade your plan or wait for next month.",
                                  details={"limit": limit, "period": period})
        return {"period": period, "reserved": tokens, "limit": limit}

    async def settle(self, user_id: str, reservation: dict, actual: int, feature: str) -> None:
        """Replace the reservation with the real usage (may be lower or higher than estimate)."""
        delta = int(actual) - int(reservation["reserved"])
        await self.db.usage.update_one(
            {"user_id": user_id, "period": reservation["period"]},
            {"$inc": {"tokens_used": delta, f"by_feature.{feature}": int(actual)}})

    async def release(self, user_id: str, reservation: dict) -> None:
        await self.db.usage.update_one(
            {"user_id": user_id, "period": reservation["period"]},
            {"$inc": {"tokens_used": -int(reservation["reserved"]), "requests": -1}})

    async def summary(self, user_id: str) -> dict:
        period = current_period()
        limit = await monthly_limit(self.db, self.s, user_id)
        doc = await self.db.usage.find_one({"user_id": user_id, "period": period}) or {}
        used = int(doc.get("tokens_used", 0))
        return {"period": period, "tokens_used": max(used, 0), "limit": limit,
                "remaining": max(limit - used, 0), "requests": int(doc.get("requests", 0)),
                "by_feature": doc.get("by_feature", {}),
                "plan_id": await effective_plan_id(self.db, user_id)}

    async def history(self, user_id: str, months: int = 6) -> list[dict]:
        cur = self.db.usage.find({"user_id": user_id}).sort("period", -1)
        docs = await cur.to_list(months)
        return [{"period": d["period"], "tokens_used": d.get("tokens_used", 0),
                 "requests": d.get("requests", 0)} for d in docs]
