"""Password hashing, JWT access tokens and opaque refresh tokens."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings
from app.core.errors import AuthError

_hasher = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _hasher.check_needs_rehash(hashed)


def create_access_token(settings: Settings, *, user_id: str, role: str, session_id: str) -> str:
    now = utcnow()
    payload = {"sub": user_id, "role": role, "sid": session_id, "typ": "access",
               "iat": now, "exp": now + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def decode_access_token(settings: Settings, token: str) -> dict:
    try:
        data = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"],
                          options={"require": ["exp", "sub", "sid"]})
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired", code="token_expired")
    except jwt.PyJWTError:
        raise AuthError("Invalid token", code="invalid_token")
    if data.get("typ") != "access":
        raise AuthError("Invalid token", code="invalid_token")
    return data


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
