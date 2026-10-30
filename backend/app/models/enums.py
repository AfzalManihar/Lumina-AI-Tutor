"""Shared constants for collections and enumerations."""
from __future__ import annotations

ROLE_STUDENT = "student"
ROLE_ADMIN = "admin"
ROLES = (ROLE_STUDENT, ROLE_ADMIN)

PLAN_FREE, PLAN_PRO, PLAN_PREMIUM = "free", "pro", "premium"

PAYMENT_PENDING, PAYMENT_SUCCEEDED, PAYMENT_FAILED, PAYMENT_CANCELLED = (
    "pending", "succeeded", "failed", "cancelled")

DOC_PROCESSING, DOC_READY, DOC_FAILED = "processing", "ready", "failed"

MEMORY_TYPES = ("preference", "goal", "topic", "progress_summary", "fact")
