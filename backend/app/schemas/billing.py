from __future__ import annotations

from pydantic import Field

from app.schemas.auth import StrictModel


class OrderIn(StrictModel):
    plan_id: str = Field(min_length=1, max_length=32)


class VerifyIn(StrictModel):
    razorpay_order_id: str = Field(min_length=1, max_length=64)
    razorpay_payment_id: str = Field(min_length=1, max_length=64)
    razorpay_signature: str = Field(min_length=1, max_length=256)
