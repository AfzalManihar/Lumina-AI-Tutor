"""Razorpay orders, signature verification, webhooks (idempotent) and subscription activation."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ConfigError, NotFoundError, ProviderError
from app.core.security import utcnow
from app.models.enums import (PAYMENT_FAILED, PAYMENT_PENDING, PAYMENT_SUCCEEDED, PLAN_FREE)
from app.services.plans import get_plans


class RazorpayClientProtocol(Protocol):
    async def create_order(self, amount_paise: int, receipt: str, notes: dict) -> dict: ...


class RazorpayClient:
    """Minimal REST client (orders only). Live use requires RAZORPAY_KEY_ID/SECRET."""

    def __init__(self, settings: Settings):
        self.s = settings

    async def create_order(self, amount_paise: int, receipt: str, notes: dict) -> dict:
        if not self.s.razorpay_configured:
            raise ConfigError("Razorpay is not configured on the server")
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"{self.s.razorpay_base_url}/orders",
                                 auth=(self.s.razorpay_key_id, self.s.razorpay_key_secret),
                                 json={"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes})
        except httpx.HTTPError:
            raise ProviderError("Payment provider unreachable")
        if r.status_code >= 400:
            raise ProviderError("Payment provider rejected the order request")
        return r.json()


def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_payment_signature(secret: str, order_id: str, payment_id: str, signature: str) -> bool:
    if not secret:
        return False
    expected = _hmac_hex(secret, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    if not secret:
        return False
    return hmac.compare_digest(_hmac_hex(secret, raw_body), signature or "")


class BillingService:
    def __init__(self, db: Any, settings: Settings, razorpay: RazorpayClientProtocol):
        self.db, self.s, self.rzp = db, settings, razorpay

    def plans(self) -> list[dict]:
        return [{"id": p.id, "name": p.name, "price_inr": p.price_inr, "monthly_token_limit": p.monthly_token_limit,
                 "max_documents": p.max_documents, "features": list(p.features)} for p in get_plans(self.s).values()]

    async def create_order(self, user_id: str, plan_id: str) -> dict:
        plans = get_plans(self.s)
        plan = plans.get(plan_id)
        if not plan or plan.id == PLAN_FREE or plan.price_inr <= 0:
            raise AppError("Plan is not purchasable", code="invalid_plan", status_code=422)
        amount = plan.price_inr * 100  # price always comes from server config
        order = await self.rzp.create_order(amount, receipt=f"u{user_id[-6:]}-{int(utcnow().timestamp())}",
                                            notes={"user_id": user_id, "plan_id": plan.id})
        await self.db.payments.insert_one({
            "user_id": user_id, "plan_id": plan.id, "amount": amount, "currency": "INR",
            "razorpay_order_id": order["id"], "razorpay_payment_id": None, "status": PAYMENT_PENDING,
            "created_at": utcnow(), "updated_at": utcnow()})
        return {"order_id": order["id"], "amount": amount, "currency": "INR",
                "key_id": self.s.razorpay_key_id, "plan_id": plan.id}

    async def _activate(self, payment: dict, payment_id: str | None) -> bool:
        """Idempotent: only the first caller flips pending -> succeeded and creates the subscription."""
        flipped = await self.db.payments.find_one_and_update(
            {"razorpay_order_id": payment["razorpay_order_id"], "status": {"$in": [PAYMENT_PENDING, PAYMENT_FAILED]}},
            {"$set": {"status": PAYMENT_SUCCEEDED, "razorpay_payment_id": payment_id, "updated_at": utcnow()}},
            return_document=True)
        if flipped is None:
            return False
        existing = await self.db.subscriptions.find_one(
            {"user_id": flipped["user_id"], "status": "active", "plan_id": flipped["plan_id"],
             "expires_at": {"$gt": utcnow()}}, sort=[("expires_at", -1)])
        start = existing["expires_at"] if existing else utcnow()
        await self.db.subscriptions.insert_one({
            "user_id": flipped["user_id"], "plan_id": flipped["plan_id"], "status": "active",
            "started_at": utcnow(), "expires_at": start + timedelta(days=self.s.plan_duration_days),
            "cancel_at_period_end": False, "payment_order_id": flipped["razorpay_order_id"]})
        await self.db.audit_events.insert_one({"user_id": flipped["user_id"], "type": "subscription_activated",
                                               "plan_id": flipped["plan_id"], "created_at": utcnow()})
        return True

    async def verify_checkout(self, user_id: str, order_id: str, payment_id: str, signature: str) -> dict:
        payment = await self.db.payments.find_one({"razorpay_order_id": order_id, "user_id": user_id})
        if not payment:
            raise NotFoundError("Order not found")
        if not verify_payment_signature(self.s.razorpay_key_secret, order_id, payment_id, signature):
            await self.db.audit_events.insert_one({"user_id": user_id, "type": "invalid_payment_signature",
                                                   "created_at": utcnow()})
            raise AppError("Payment signature verification failed", code="invalid_signature", status_code=400)
        activated = await self._activate(payment, payment_id)
        return {"status": PAYMENT_SUCCEEDED, "newly_activated": activated}

    async def handle_webhook(self, raw_body: bytes, signature: str, event_id: str | None) -> dict:
        if not verify_webhook_signature(self.s.razorpay_webhook_secret, raw_body, signature):
            raise AppError("Invalid webhook signature", code="invalid_signature", status_code=400)
        try:
            event = json.loads(raw_body)
        except ValueError:
            raise AppError("Malformed webhook body", code="bad_payload", status_code=400)
        key = event_id or hashlib.sha256(raw_body).hexdigest()
        try:
            await self.db.webhook_events.insert_one({"event_key": key, "event": event.get("event"),
                                                     "received_at": utcnow()})
        except Exception as e:  # noqa: BLE001
            if "duplicate" in str(e).lower() or "E11000" in str(e):
                return {"status": "duplicate_ignored"}
            raise
        name = event.get("event", "")
        ent = (event.get("payload", {}).get("payment", {}) or {}).get("entity", {}) or {}
        order_id, pay_id = ent.get("order_id"), ent.get("id")
        if not order_id:
            order_id = ((event.get("payload", {}).get("order", {}) or {}).get("entity", {}) or {}).get("id")
        payment = await self.db.payments.find_one({"razorpay_order_id": order_id}) if order_id else None
        if not payment:
            return {"status": "ignored_unknown_order"}
        if name in ("payment.captured", "order.paid"):
            if ent.get("amount") is not None and int(ent["amount"]) != int(payment["amount"]):
                return {"status": "ignored_amount_mismatch"}
            return {"status": "activated" if await self._activate(payment, pay_id) else "already_processed"}
        if name == "payment.failed":
            await self.db.payments.update_one(
                {"razorpay_order_id": order_id, "status": PAYMENT_PENDING},
                {"$set": {"status": PAYMENT_FAILED, "razorpay_payment_id": pay_id, "updated_at": utcnow()}})
            return {"status": "marked_failed"}
        return {"status": "ignored_event"}

    async def cancel(self, user_id: str) -> dict:
        res = await self.db.subscriptions.update_many(
            {"user_id": user_id, "status": "active", "expires_at": {"$gt": utcnow()}},
            {"$set": {"cancel_at_period_end": True}})
        return {"cancel_at_period_end": res.modified_count > 0}

    async def subscription(self, user_id: str) -> dict:
        sub = await self.db.subscriptions.find_one(
            {"user_id": user_id, "status": "active", "expires_at": {"$gt": utcnow()}}, sort=[("expires_at", -1)])
        if not sub:
            return {"plan_id": PLAN_FREE, "status": "free", "expires_at": None, "cancel_at_period_end": False}
        return {"plan_id": sub["plan_id"], "status": "active", "expires_at": sub["expires_at"],
                "cancel_at_period_end": sub.get("cancel_at_period_end", False)}

    async def history(self, user_id: str, limit: int = 50, skip: int = 0) -> list[dict]:
        docs = await self.db.payments.find({"user_id": user_id}).sort("created_at", -1).skip(skip).to_list(limit)
        return [{"order_id": d["razorpay_order_id"], "plan_id": d["plan_id"], "amount": d["amount"],
                 "currency": d["currency"], "status": d["status"], "created_at": d["created_at"]} for d in docs]
