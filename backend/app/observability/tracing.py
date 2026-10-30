
"""Structured tracing for Lumina AI Tutor with optional Langfuse delivery.

Only explicitly selected metadata is exported. Prompts, answers, and secrets
are never sent to Langfuse.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

log = logging.getLogger("lumina.trace")

_SECRET_PATTERNS = [
    re.compile(r"(?i)bearer\s+[a-z0-9._-]+"),
    re.compile(r"\bgsk_[A-Za-z0-9]{10,}\b"),
    re.compile(r"\brzp_(?:test|live)_[A-Za-z0-9]{6,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
]


def redact(text: str, secrets: list[str] | None = None) -> str:
    for secret in secrets or []:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def user_hash(user_id: str) -> str:
    return hashlib.sha256(
        ("lumina-trace:" + user_id).encode()
    ).hexdigest()[:12]


@dataclass
class Span:
    name: str
    kind: str
    started: float = field(default_factory=time.perf_counter)
    duration_ms: float = 0.0
    status: str = "ok"
    attrs: dict[str, Any] = field(default_factory=dict)


@lru_cache(maxsize=1)
def _langfuse_client():
    """Create the Langfuse client using application settings."""
    settings = get_settings()

    if not settings.langfuse_enabled:
        return None

    if not (
        settings.langfuse_public_key
        and settings.langfuse_secret_key
        and settings.langfuse_host
    ):
        log.warning("Langfuse enabled but configuration is incomplete")
        return None

    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host.rstrip("/"),
        )
    except Exception:
        log.exception("Could not initialize Langfuse client")
        return None


def _send_to_langfuse(summary: dict[str, Any]) -> None:
    """Export selected metadata without breaking the main application."""
    client = _langfuse_client()
    if client is None:
        return

    try:
        metadata = {
            "workflow": str(summary.get("workflow", "unknown"))[:100],
            "request_id": str(summary.get("request_id") or "")[:100],
            "steps": [
                str(name)[:100]
                for name in summary.get("steps", [])[:30]
            ],
            "latency_ms": summary.get("latency_ms", 0),
            "retries": summary.get("retries", 0),
            "tokens": summary.get("tokens", {}),
            "error_category": summary.get("error_category"),
            "span_count": len(summary.get("spans", [])),
        }

        observation = client.start_observation(
            name=str(summary.get("workflow", "lumina-workflow"))[:100],
            as_type="span",
            metadata=metadata,
        )
        observation.update(
            output={
                "status": "error" if summary.get("error_category") else "ok",
                "trace_id": summary.get("trace_id"),
            }
        )
        observation.end()
        client.flush()
    except Exception:
        log.exception("Langfuse trace delivery failed")


class Trace:
    """One workflow execution; attributes should contain metadata only."""

    def __init__(
        self,
        workflow: str,
        user_id: str | None = None,
        request_id: str | None = None,
    ):
        self.trace_id = uuid.uuid4().hex
        self.request_id = request_id
        self.workflow = workflow
        self.user = user_hash(user_id) if user_id else None
        self.spans: list[Span] = []
        self.started = time.perf_counter()
        self.retries = 0
        self.tokens = {"prompt": 0, "completion": 0, "total": 0}
        self.error_category: str | None = None

    def span(self, name: str, kind: str, **attrs: Any) -> _SpanCtx:
        return _SpanCtx(
            self,
            Span(name=name, kind=kind, attrs=dict(attrs)),
        )

    def add_usage(self, usage: dict | None) -> None:
        if not usage:
            return
        for key in ("prompt", "completion", "total"):
            self.tokens[key] += int(usage.get(key, 0) or 0)

    def summary(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "workflow": self.workflow,
            "user": self.user,
            "latency_ms": round(
                (time.perf_counter() - self.started) * 1000, 1
            ),
            "steps": [span.name for span in self.spans],
            "spans": [
                {
                    "name": span.name,
                    "kind": span.kind,
                    "status": span.status,
                    "duration_ms": round(span.duration_ms, 1),
                    **span.attrs,
                }
                for span in self.spans
            ],
            "retries": self.retries,
            "tokens": dict(self.tokens),
            "error_category": self.error_category,
        }

    def emit(self) -> dict[str, Any]:
        result = self.summary()
        log.info(json.dumps(result, default=str))
        _send_to_langfuse(result)
        return result


class _SpanCtx:
    def __init__(self, trace: Trace, span: Span):
        self.trace = trace
        self.span = span

    def __enter__(self) -> Span:
        self.span.started = time.perf_counter()
        return self.span

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.span.duration_ms = (
            time.perf_counter() - self.span.started
        ) * 1000

        if exc_type is not None:
            self.span.status = "error"
            self.span.attrs["error"] = exc_type.__name__
            self.trace.error_category = exc_type.__name__

        self.trace.spans.append(self.span)
        return False


def langfuse_status(settings) -> dict[str, Any]:
    if not settings.langfuse_enabled:
        return {"state": "disabled"}

    if (
        settings.langfuse_public_key
        and settings.langfuse_secret_key
        and settings.langfuse_host
    ):
        return {"state": "configured", "delivery": "not_implemented"}

    return {
        "state": "misconfigured",
        "detail": "Langfuse keys or host are missing",
    }


async def verify_langfuse(settings) -> dict[str, Any]:
    """Check host reachability; this alone does not verify API credentials."""
    status = langfuse_status(settings)
    if status["state"] != "configured":
        return status

    import httpx

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                settings.langfuse_host.rstrip("/") + "/api/public/health"
            )

        if response.status_code == 200:
            return {
                "state": "verified_reachable",
                "delivery": "enabled",
            }

        return {
            "state": "configured",
            "reachable": False,
            "status": response.status_code,
        }
    except Exception as exc:
        return {
            "state": "configured",
            "reachable": False,
            "error": type(exc).__name__,
        }
