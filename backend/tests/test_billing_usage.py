import asyncio
import json

import pytest

from app.core.errors import UsageLimitError
from app.services.usage import UsageService
from tests.conftest import make_settings, register, sign_payment, sign_webhook


async def _order(c, plan="pro"):
    r = await c.post("/api/v1/billing/orders", json={"plan_id": plan})
    assert r.status_code == 200, r.text
    return r.json()


async def test_plans_from_config(client):
    r = await client.get("/api/v1/billing/plans")
    ids = [p["id"] for p in r.json()["plans"]]
    assert ids == ["free", "pro", "premium"]


async def test_order_price_is_server_side_and_free_not_purchasable(client, razorpay):
    await register(client)
    o = await _order(client, "pro")
    assert o["amount"] == 499 * 100 and razorpay.orders[0]["amount"] == 49900
    r = await client.post("/api/v1/billing/orders", json={"plan_id": "free"})
    assert r.status_code == 422
    r = await client.post("/api/v1/billing/orders", json={"plan_id": "nope"})
    assert r.status_code == 422
    r = await client.post("/api/v1/billing/orders", json={"plan_id": "pro", "amount": 1})
    assert r.status_code == 422  # client cannot supply an amount


async def test_checkout_invalid_signature_grants_nothing(client):
    await register(client)
    o = await _order(client)
    r = await client.post("/api/v1/billing/verify", json={
        "razorpay_order_id": o["order_id"], "razorpay_payment_id": "pay_1", "razorpay_signature": "deadbeef"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_signature"
    sub = (await client.get("/api/v1/billing/subscription")).json()
    assert sub["plan_id"] == "free"


async def test_checkout_valid_signature_activates_once(client):
    await register(client)
    o = await _order(client)
    sig = sign_payment(o["order_id"], "pay_1")
    body = {"razorpay_order_id": o["order_id"], "razorpay_payment_id": "pay_1", "razorpay_signature": sig}
    r1 = await client.post("/api/v1/billing/verify", json=body)
    r2 = await client.post("/api/v1/billing/verify", json=body)
    assert r1.json()["newly_activated"] is True and r2.json()["newly_activated"] is False
    sub = (await client.get("/api/v1/billing/subscription")).json()
    assert sub["plan_id"] == "pro" and sub["status"] == "active"
    hist = (await client.get("/api/v1/billing/history")).json()["items"]
    assert len(hist) == 1 and hist[0]["status"] == "succeeded"
    usage = (await client.get("/api/v1/usage")).json()
    assert usage["current"]["limit"] == 1_000_000  # effective plan drives the limit


async def test_cannot_verify_another_users_order(make_client):
    a, b = await make_client(), await make_client()
    await register(a)
    await register(b)
    o = await _order(a)
    r = await b.post("/api/v1/billing/verify", json={
        "razorpay_order_id": o["order_id"], "razorpay_payment_id": "pay_x",
        "razorpay_signature": sign_payment(o["order_id"], "pay_x")})
    assert r.status_code == 404
    assert (await b.get("/api/v1/billing/subscription")).json()["plan_id"] == "free"
    assert (await b.get("/api/v1/billing/history")).json()["items"] == []


def _event(order_id, name="payment.captured", pay="pay_w1", amount=49900):
    return json.dumps({"event": name, "payload": {"payment": {"entity": {
        "id": pay, "order_id": order_id, "amount": amount}}}}).encode()


async def test_webhook_signature_required(client):
    await register(client)
    o = await _order(client)
    raw = _event(o["order_id"])
    r = await client.post("/api/v1/billing/webhook", content=raw, headers={"X-Razorpay-Signature": "bad"})
    assert r.status_code == 400
    r = await client.post("/api/v1/billing/webhook", content=raw)
    assert r.status_code == 400
    assert (await client.get("/api/v1/billing/subscription")).json()["plan_id"] == "free"


async def test_webhook_activates_and_is_idempotent(client, db):
    await register(client)
    o = await _order(client)
    raw = _event(o["order_id"])
    h = {"X-Razorpay-Signature": sign_webhook(raw), "X-Razorpay-Event-Id": "evt_1"}
    r1 = await client.post("/api/v1/billing/webhook", content=raw, headers=h)
    r2 = await client.post("/api/v1/billing/webhook", content=raw, headers=h)  # duplicate delivery
    assert r1.json()["status"] == "activated" and r2.json()["status"] == "duplicate_ignored"
    # same payment re-sent under a different event id must not create a second subscription
    h2 = {"X-Razorpay-Signature": sign_webhook(raw), "X-Razorpay-Event-Id": "evt_2"}
    r3 = await client.post("/api/v1/billing/webhook", content=raw, headers=h2)
    assert r3.json()["status"] == "already_processed"
    assert await db.subscriptions.count_documents({}) == 1


async def test_webhook_amount_mismatch_and_failed(client):
    await register(client)
    o = await _order(client)
    raw = _event(o["order_id"], amount=100)
    r = await client.post("/api/v1/billing/webhook", content=raw,
                          headers={"X-Razorpay-Signature": sign_webhook(raw), "X-Razorpay-Event-Id": "e1"})
    assert r.json()["status"] == "ignored_amount_mismatch"
    assert (await client.get("/api/v1/billing/subscription")).json()["plan_id"] == "free"
    raw = _event(o["order_id"], name="payment.failed")
    r = await client.post("/api/v1/billing/webhook", content=raw,
                          headers={"X-Razorpay-Signature": sign_webhook(raw), "X-Razorpay-Event-Id": "e2"})
    assert r.json()["status"] == "marked_failed"
    assert (await client.get("/api/v1/billing/history")).json()["items"][0]["status"] == "failed"


async def test_cancel_keeps_access_until_expiry(client):
    await register(client)
    o = await _order(client)
    await client.post("/api/v1/billing/verify", json={
        "razorpay_order_id": o["order_id"], "razorpay_payment_id": "p", "razorpay_signature": sign_payment(o["order_id"], "p")})
    assert (await client.post("/api/v1/billing/cancel")).json()["cancel_at_period_end"] is True
    sub = (await client.get("/api/v1/billing/subscription")).json()
    assert sub["status"] == "active" and sub["cancel_at_period_end"] is True


async def test_expired_subscription_falls_back_to_free(client, db):
    from datetime import timedelta
    from app.core.security import utcnow
    body = await register(client)
    await db.subscriptions.insert_one({"user_id": body["user"]["id"], "plan_id": "pro", "status": "active",
                                       "expires_at": utcnow() - timedelta(days=1)})
    assert (await client.get("/api/v1/billing/subscription")).json()["plan_id"] == "free"


async def test_usage_limit_enforced_and_settled(db):
    s = make_settings(user_monthly_token_limit=1000)
    svc = UsageService(db, s)
    r1 = await svc.reserve("u1", 600)
    with pytest.raises(UsageLimitError):
        await svc.reserve("u1", 600)
    await svc.settle("u1", r1, 300, "chat")  # actual usage lower than estimate frees allowance
    r2 = await svc.reserve("u1", 600)
    assert (await svc.summary("u1"))["tokens_used"] == 900
    await svc.release("u1", r2)
    assert (await svc.summary("u1"))["tokens_used"] == 300


async def test_concurrent_reservations_never_exceed_limit(db):
    s = make_settings(user_monthly_token_limit=1000)
    svc = UsageService(db, s)

    async def attempt():
        try:
            await svc.reserve("u2", 100)
            return True
        except UsageLimitError:
            return False

    results = await asyncio.gather(*[attempt() for _ in range(25)])
    assert sum(results) == 10
    assert (await svc.summary("u2"))["tokens_used"] == 1000
