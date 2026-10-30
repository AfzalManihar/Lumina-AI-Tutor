"""Lumina AI Tutor - FastAPI application factory."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.errors import RateLimitError, install_error_handlers
from app.core.ratelimit import SlidingWindowLimiter
from app.db.mongo import create_client, ensure_indexes, ping
from app.services.billing import RazorpayClient

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("lumina")


async def _ensure_indexes_once(app: FastAPI) -> bool:
    """Create indexes if not done yet. Unique indexes back email uniqueness, webhook idempotency and usage rows,
    so write requests are refused (503) until this has succeeded."""
    if getattr(app.state, "indexes_ready", False):
        return True
    try:
        await ensure_indexes(app.state.db)
    except Exception as e:  # noqa: BLE001
        log.warning("index creation failed: %s", type(e).__name__)
        return False
    app.state.indexes_ready = True
    return True


def create_app(settings: Settings | None = None, db: Any | None = None, razorpay: Any | None = None,
               llm: Any | None = None, embedder: Any | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = None
        if db is None:
            client = create_client(settings)
            app.state.db = client[settings.db_name]
        else:
            app.state.db = db
        if not await _ensure_indexes_once(app):
            log.warning("indexes not created yet (database unreachable); writes are refused until they exist")
        yield
        if client is not None:
            await client.close()

    app = FastAPI(title="Lumina AI Tutor API", version="1.0.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.razorpay = razorpay or RazorpayClient(settings)
    app.state.llm_override = llm
    app.state.embedder_override = embedder
    app.state.api_limiter = SlidingWindowLimiter(settings.api_rate_limit_per_minute)
    app.state.indexes_ready = False
    if db is not None:
        app.state.db = db  # available even when the lifespan has not been started

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                       allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
                       expose_headers=["X-Request-ID"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex
        try:
            if request.url.path.startswith("/api/v1") and request.url.path != "/api/v1/billing/webhook":
                ip = request.client.host if request.client else "unknown"
                app.state.api_limiter.check(ip)
        except RateLimitError as e:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": {"code": e.code, "message": e.message,
                                           "request_id": request.state.request_id}}, status_code=429,
                                headers={"Retry-After": str(e.details.get("retry_after", 60)),
                                         "X-Request-ID": request.state.request_id})
        if (request.url.path.startswith("/api/v1") and request.method not in ("GET", "HEAD", "OPTIONS")
                and not await _ensure_indexes_once(app)):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": {"code": "service_unavailable", "request_id": request.state.request_id,
                                           "message": "The database is not ready. Please try again shortly."}},
                                status_code=503, headers={"Retry-After": "5", "X-Request-ID": request.state.request_id})
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    install_error_handlers(app)

    v1 = APIRouter(prefix="/api/v1")
    from app.api import auth, billing, users
    v1.include_router(auth.router)
    v1.include_router(users.router)
    v1.include_router(billing.router)
    _mount_optional(v1)
    app.include_router(v1)

    @app.get("/health", tags=["ops"])
    async def health():
        return {"status": "ok"}

    @app.get("/ready", tags=["ops"])
    async def ready(request: Request):
        ok = await ping(request.app.state.db)
        idx = ok and await _ensure_indexes_once(request.app)
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "ready" if idx else "degraded", "database": "up" if ok else "down",
                             "indexes": "ready" if idx else "pending"}, status_code=200 if idx else 503)

    _serve_frontend(app)
    return app


def _serve_frontend(app: FastAPI) -> None:
    """Optionally serve the built React app from this process (single-container deploys, same origin as the API).
    Enabled only when STATIC_DIR points at a directory containing index.html; API, docs and ops routes always win."""
    import os
    from pathlib import Path

    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    root = Path(os.environ.get("STATIC_DIR", "")).resolve() if os.environ.get("STATIC_DIR") else None
    if not root or not (root / "index.html").is_file():
        return
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/") or path in ("api", "health", "ready"):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)
        target = (root / path).resolve()
        if path and root in target.parents and target.is_file():
            return FileResponse(target)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})


def _mount_optional(v1: APIRouter) -> None:
    """Routers added in later modules; imported lazily so partial builds still start."""
    import importlib
    for name in ("documents", "memory", "tutor", "learning", "admin"):
        try:
            mod = importlib.import_module(f"app.api.{name}")
        except ModuleNotFoundError as e:
            if e.name == f"app.api.{name}":
                continue
            raise
        v1.include_router(mod.router)


def app_factory() -> FastAPI:  # uvicorn --factory app.main:app_factory
    return create_app()
