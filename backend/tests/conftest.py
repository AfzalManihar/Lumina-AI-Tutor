from __future__ import annotations

import hashlib
import hmac
import itertools

import httpx
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient

from app.core.config import Settings
from app.db.mongo import ensure_indexes
from app.main import create_app

WEBHOOK_SECRET = "whsec_test_secret_value"
KEY_SECRET = "rzp_test_secret_value"


class FakeRazorpay:
    """Mocked Razorpay: never touches the network."""
    def __init__(self):
        self._n = itertools.count(1)
        self.orders: list[dict] = []

    async def create_order(self, amount_paise, receipt, notes):
        order = {"id": f"order_test_{next(self._n)}", "amount": amount_paise, "currency": "INR"}
        self.orders.append(order)
        return order


def make_settings(**over) -> Settings:
    base = dict(app_env="test", app_secret_key="test-secret-key-0123456789-abcdefghijklmnop",
                razorpay_key_id="rzp_test_key", razorpay_key_secret=KEY_SECRET,
                razorpay_webhook_secret=WEBHOOK_SECRET, embedding_provider="hash",
                vector_store_provider="mongo", groq_api_key="gsk_test_not_real_key_123456",
                api_rate_limit_per_minute=10000, _env_file=None)
    base.update(over)
    return Settings(**base)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest_asyncio.fixture
async def db():
    client = AsyncMongoMockClient(tz_aware=True)
    database = client["lumina_test"]
    await ensure_indexes(database)
    return database


@pytest.fixture
def razorpay() -> FakeRazorpay:
    return FakeRazorpay()


@pytest.fixture
def llm():
    from tests.fakes import FakeLLM
    return FakeLLM()


@pytest_asyncio.fixture
async def app(settings, db, razorpay, llm):
    return create_app(settings, db=db, razorpay=razorpay, llm=llm)


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def make_client(app):
    """Factory for independent clients (separate cookie jars) - used for cross-user tests."""
    clients: list[httpx.AsyncClient] = []

    async def _make():
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        return c

    yield _make
    for c in clients:
        await c.aclose()


_counter = itertools.count(1)


async def register(c: httpx.AsyncClient, email: str | None = None, password: str = "Passw0rd123") -> dict:
    email = email or f"user{next(_counter)}@example.com"
    r = await c.post("/api/v1/auth/register", json={"email": email, "password": password, "name": "T"})
    assert r.status_code == 201, r.text
    body = r.json()
    c.headers["Authorization"] = f"Bearer {body['access_token']}"
    body["email"] = email
    return body


def sign_webhook(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def sign_payment(order_id: str, payment_id: str, secret: str = KEY_SECRET) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
