"""Registration, login, refresh-token rotation and logout."""
from __future__ import annotations

import re
import uuid
from datetime import timedelta
from typing import Any

from bson import ObjectId

from app.core.config import Settings
from app.core.errors import AuthError, ConflictError
from app.core.ratelimit import LoginThrottle
from app.core.security import (create_access_token, hash_password, hash_token, new_refresh_token,
                               needs_rehash, utcnow, verify_password)
from app.models.enums import ROLE_STUDENT

# Verified against this when the account does not exist, to keep timing similar.
_DUMMY_HASH = hash_password("dummy-password-for-timing-1")


def validate_password_strength(pw: str) -> None:
    from app.core.errors import AppError
    if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise AppError("Password must be at least 8 characters and contain a letter and a digit",
                       code="weak_password", status_code=422)


def public_user(u: dict) -> dict:
    return {"id": str(u["_id"]), "email": u["email"], "name": u.get("name", ""), "role": u["role"],
            "created_at": u["created_at"], "settings": u.get("settings", {})}


class AuthService:
    def __init__(self, db: Any, settings: Settings):
        self.db, self.s = db, settings
        self.throttle = LoginThrottle(db, settings)

    async def register(self, email: str, password: str, name: str) -> dict:
        validate_password_strength(password)
        email = email.lower().strip()
        doc = {"email": email, "name": name.strip(), "password_hash": hash_password(password),
               "role": ROLE_STUDENT, "created_at": utcnow(), "updated_at": utcnow(),
               "settings": {"memory_enabled": self.s.memory_enabled, "learning_topic": ""}}
        try:
            res = await self.db.users.insert_one(doc)
        except Exception as e:  # duplicate key
            if "duplicate" in str(e).lower() or "E11000" in str(e):
                raise ConflictError("An account with this email already exists", code="email_taken")
            raise
        doc["_id"] = res.inserted_id
        return doc

    async def _new_session(self, user: dict, meta: dict) -> tuple[str, str, str]:
        refresh = new_refresh_token()
        sid = uuid.uuid4().hex
        await self.db.sessions.insert_one({
            "sid": sid, "user_id": str(user["_id"]), "refresh_hash": hash_token(refresh), "revoked": False,
            "created_at": utcnow(), "expires_at": utcnow() + timedelta(days=self.s.refresh_token_days),
            "user_agent": (meta.get("user_agent") or "")[:200]})
        access = create_access_token(self.s, user_id=str(user["_id"]), role=user["role"], session_id=sid)
        return access, refresh, sid

    async def login(self, email: str, password: str, meta: dict) -> tuple[dict, str, str]:
        email = email.lower().strip()
        key = f"{email}|{meta.get('ip', '')}"
        await self.throttle.check(key)
        user = await self.db.users.find_one({"email": email})
        ok = verify_password(password, user["password_hash"] if user else _DUMMY_HASH)
        if not user or not ok or user.get("disabled"):
            await self.throttle.record_failure(key)
            raise AuthError("Invalid email or password", code="invalid_credentials")
        await self.throttle.reset(key)
        if needs_rehash(user["password_hash"]):
            await self.db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(password)}})
        access, refresh, _ = await self._new_session(user, meta)
        return user, access, refresh

    async def refresh(self, refresh_token: str, meta: dict) -> tuple[dict, str, str]:
        h = hash_token(refresh_token)
        sess = await self.db.sessions.find_one({"refresh_hash": h})
        if not sess:
            reused = await self.db.sessions.find_one({"prev_hashes": h})
            if reused:
                # A rotated-out token was replayed: assume theft, revoke every session for that user.
                await self.db.sessions.update_many({"user_id": reused["user_id"]}, {"$set": {"revoked": True}})
            raise AuthError("Invalid session", code="invalid_session")
        if sess["revoked"]:
            # Reuse of a revoked token: assume theft, revoke every session for that user.
            await self.db.sessions.update_many({"user_id": sess["user_id"]}, {"$set": {"revoked": True}})
            raise AuthError("Invalid session", code="invalid_session")
        if sess["expires_at"] <= utcnow():
            raise AuthError("Session expired", code="session_expired")
        user = await self.db.users.find_one({"_id": ObjectId(sess["user_id"])})
        if not user or user.get("disabled"):
            raise AuthError("Invalid session", code="invalid_session")
        new_refresh = new_refresh_token()
        # Rotate atomically: only succeeds once per refresh token.
        res = await self.db.sessions.update_one(
            {"_id": sess["_id"], "refresh_hash": h, "revoked": False},
            {"$set": {"refresh_hash": hash_token(new_refresh),
                      "expires_at": utcnow() + timedelta(days=self.s.refresh_token_days)},
             "$push": {"prev_hashes": {"$each": [h], "$slice": -20}}})
        if res.modified_count != 1:
            raise AuthError("Invalid session", code="invalid_session")
        access = create_access_token(self.s, user_id=str(user["_id"]), role=user["role"], session_id=sess["sid"])
        return user, access, new_refresh

    async def logout(self, session_id: str) -> None:
        await self.db.sessions.update_one({"sid": session_id}, {"$set": {"revoked": True}})

    async def logout_all(self, user_id: str) -> None:
        await self.db.sessions.update_many({"user_id": user_id}, {"$set": {"revoked": True}})

    async def change_password(self, user: dict, old: str, new: str) -> None:
        if not verify_password(old, user["password_hash"]):
            raise AuthError("Current password is incorrect", code="invalid_credentials")
        validate_password_strength(new)
        await self.db.users.update_one({"_id": user["_id"]},
                                       {"$set": {"password_hash": hash_password(new), "updated_at": utcnow()}})
        await self.logout_all(str(user["_id"]))
