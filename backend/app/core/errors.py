"""Application errors and safe error responses."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("lumina.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str = "Bad request", *, code: str | None = None,
                 status_code: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class UsageLimitError(AppError):
    status_code = 402
    code = "usage_limit_exceeded"


class GuardrailError(AppError):
    status_code = 422
    code = "guardrail_blocked"


class ProviderError(AppError):
    status_code = 502
    code = "provider_error"


class ConfigError(AppError):
    status_code = 503
    code = "not_configured"


def _body(code: str, message: str, request: Request, details: dict | None = None) -> dict:
    out = {"error": {"code": code, "message": message,
                     "request_id": getattr(request.state, "request_id", None)}}
    if details:
        out["error"]["details"] = details
    return out


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        headers = {}
        if exc.details.get("retry_after"):
            headers["Retry-After"] = str(exc.details["retry_after"])
        return JSONResponse(_body(exc.code, exc.message, request, exc.details),
                            status_code=exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = [{"loc": [str(p) for p in e.get("loc", [])][1:], "msg": e.get("msg", "invalid")}
                  for e in exc.errors()]
        return JSONResponse(_body("validation_error", "Request validation failed", request,
                                  {"fields": fields}), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body("http_error", str(exc.detail), request), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(_body("internal_error", "An internal error occurred", request), status_code=500)
