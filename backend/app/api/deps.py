"""FastAPI dependencies: settings, DB, authentication, authorization."""
from __future__ import annotations

from typing import Any

from bson import ObjectId
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.errors import AuthError, ForbiddenError
from app.core.security import decode_access_token, utcnow
from app.models.enums import ROLE_ADMIN

bearer = HTTPBearer(auto_error=False)


def settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def db_dep(request: Request) -> Any:
    return request.app.state.db


async def current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                       settings: Settings = Depends(settings_dep), db: Any = Depends(db_dep)) -> dict:
    """Identity is derived only from the verified token + live server-side session."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthError("Authentication required")
    data = decode_access_token(settings, creds.credentials)
    sess = await db.sessions.find_one({"sid": data["sid"], "user_id": data["sub"]})
    if not sess or sess["revoked"] or sess["expires_at"] <= utcnow():
        raise AuthError("Session is no longer valid", code="invalid_session")
    try:
        user = await db.users.find_one({"_id": ObjectId(data["sub"])})
    except Exception:  # noqa: BLE001
        user = None
    if not user or user.get("disabled"):
        raise AuthError("Account not available")
    user["_sid"] = data["sid"]
    request.state.user_id = str(user["_id"])
    return user


async def admin_user(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != ROLE_ADMIN:  # role always read from DB, not from the token
        raise ForbiddenError("Administrator access required")
    return user


def uid(user: dict) -> str:
    return str(user["_id"])
