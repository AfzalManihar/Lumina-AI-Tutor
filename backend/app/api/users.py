from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from app.api.deps import current_user, db_dep, settings_dep
from app.core.config import Settings
from app.core.security import utcnow
from app.schemas.auth import PasswordChange, ProfileUpdate, UserOut
from app.services.auth import AuthService, public_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: ProfileUpdate, user: dict = Depends(current_user), db: Any = Depends(db_dep)):
    sets: dict = {"updated_at": utcnow()}
    if body.name is not None:
        sets["name"] = body.name
    if body.settings is not None:
        sets["settings"] = body.settings.model_dump()
    await db.users.update_one({"_id": user["_id"]}, {"$set": sets})
    return public_user(await db.users.find_one({"_id": user["_id"]}))


@router.post("/me/password", status_code=204)
async def change_password(body: PasswordChange, user: dict = Depends(current_user),
                          db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    await AuthService(db, s).change_password(user, body.old_password, body.new_password)
    return Response(status_code=204)
