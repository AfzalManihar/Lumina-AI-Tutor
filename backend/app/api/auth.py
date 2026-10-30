from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import current_user, db_dep, settings_dep, uid
from app.core.config import Settings
from app.core.errors import AuthError
from app.schemas.auth import LoginIn, RegisterIn, TokenOut
from app.services.auth import AuthService, public_user

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "lumina_refresh"


def _set_cookie(resp: Response, token: str, s: Settings) -> None:
    resp.set_cookie(COOKIE, token, max_age=s.refresh_token_days * 86400, httponly=True,
                    secure=s.app_env == "production", samesite="strict", path="/api/v1/auth")


def _meta(request: Request) -> dict:
    return {"ip": request.client.host if request.client else "", "user_agent": request.headers.get("user-agent", "")}


def _token_out(user: dict, access: str, s: Settings) -> dict:
    return {"access_token": access, "expires_in": s.access_token_minutes * 60, "user": public_user(user)}


def _csrf_guard(request: Request) -> None:
    # Cookie-authenticated endpoint: require a custom header (cannot be set cross-site without CORS preflight).
    if request.headers.get("x-requested-with") != "lumina":
        raise AuthError("Missing CSRF header", code="csrf")


@router.post("/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, request: Request, response: Response,
                   db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    svc = AuthService(db, s)
    await svc.register(body.email, body.password, body.name)
    user, access, refresh = await svc.login(body.email, body.password, _meta(request))
    _set_cookie(response, refresh, s)
    return _token_out(user, access, s)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response,
                db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    user, access, refresh = await AuthService(db, s).login(body.email, body.password, _meta(request))
    _set_cookie(response, refresh, s)
    return _token_out(user, access, s)


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response, db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    _csrf_guard(request)
    token = request.cookies.get(COOKIE)
    if not token:
        raise AuthError("No session", code="no_session")
    user, access, new_refresh = await AuthService(db, s).refresh(token, _meta(request))
    _set_cookie(response, new_refresh, s)
    return _token_out(user, access, s)


@router.post("/logout", status_code=204)
async def logout(response: Response, user: dict = Depends(current_user),
                 db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    await AuthService(db, s).logout(user["_sid"])
    response.delete_cookie(COOKIE, path="/api/v1/auth")
    response.status_code = 204
    return response


@router.post("/logout-all", status_code=204)
async def logout_all(response: Response, user: dict = Depends(current_user),
                     db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    await AuthService(db, s).logout_all(uid(user))
    response.delete_cookie(COOKIE, path="/api/v1/auth")
    response.status_code = 204
    return response
