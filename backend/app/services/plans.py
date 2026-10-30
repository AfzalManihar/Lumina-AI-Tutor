"""Subscription plan catalogue, derived from configuration (single source of truth)."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.models.enums import PLAN_FREE, PLAN_PREMIUM, PLAN_PRO


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_inr: int
    monthly_token_limit: int
    max_documents: int
    features: tuple[str, ...]


def get_plans(s: Settings) -> dict[str, Plan]:
    return {
        PLAN_FREE: Plan(PLAN_FREE, "Free", 0, s.user_monthly_token_limit, 3,
                        ("AI tutor chat", "Lessons & quizzes", "3 documents")),
        PLAN_PRO: Plan(PLAN_PRO, "Pro", s.plan_pro_price_inr, s.plan_pro_monthly_token_limit, 25,
                       ("Higher token allowance", "25 documents", "Priority limits")),
        PLAN_PREMIUM: Plan(PLAN_PREMIUM, "Premium", s.plan_premium_price_inr,
                           s.plan_premium_monthly_token_limit, 100,
                           ("Highest token allowance", "100 documents")),
    }
