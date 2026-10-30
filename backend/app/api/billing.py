from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.deps import current_user, db_dep, settings_dep, uid
from app.core.config import Settings
from app.schemas.billing import OrderIn, VerifyIn
from app.services.billing import BillingService
from app.services.usage import UsageService

router = APIRouter(tags=["billing"])


def billing_dep(request: Request, db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)) -> BillingService:
    return BillingService(db, s, request.app.state.razorpay)


@router.get("/billing/plans")
async def plans(svc: BillingService = Depends(billing_dep)):
    return {"plans": svc.plans()}


@router.get("/billing/subscription")
async def subscription(user: dict = Depends(current_user), svc: BillingService = Depends(billing_dep)):
    return await svc.subscription(uid(user))


@router.post("/billing/orders")
async def create_order(body: OrderIn, user: dict = Depends(current_user), svc: BillingService = Depends(billing_dep)):
    return await svc.create_order(uid(user), body.plan_id)


@router.post("/billing/verify")
async def verify(body: VerifyIn, user: dict = Depends(current_user), svc: BillingService = Depends(billing_dep)):
    return await svc.verify_checkout(uid(user), body.razorpay_order_id, body.razorpay_payment_id,
                                     body.razorpay_signature)


@router.post("/billing/cancel")
async def cancel(user: dict = Depends(current_user), svc: BillingService = Depends(billing_dep)):
    return await svc.cancel(uid(user))


@router.get("/billing/history")
async def history(limit: int = Query(50, ge=1, le=100), skip: int = Query(0, ge=0),
                  user: dict = Depends(current_user), svc: BillingService = Depends(billing_dep)):
    return {"items": await svc.history(uid(user), limit, skip)}


@router.post("/billing/webhook")
async def webhook(request: Request, x_razorpay_signature: str = Header(default=""),
                  x_razorpay_event_id: str | None = Header(default=None),
                  svc: BillingService = Depends(billing_dep)):
    raw = await request.body()  # signature is computed over the raw bytes
    return await svc.handle_webhook(raw, x_razorpay_signature, x_razorpay_event_id)


@router.get("/usage")
async def usage(user: dict = Depends(current_user), db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    svc = UsageService(db, s)
    return {"current": await svc.summary(uid(user)), "history": await svc.history(uid(user))}
