"""Administrator diagnostics. Role is checked server-side from the database on every request."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import admin_user, db_dep, settings_dep
from app.core.config import Settings
from app.db.mongo import ping
from app.observability.tracing import langfuse_status, verify_langfuse
from app.services.usage import effective_plan_id
from app.tools.registry import REGISTRY

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/diagnostics")
async def diagnostics(_: dict = Depends(admin_user), db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    # Reports only whether secrets are configured - never their values.
    return {
        "database": "up" if await ping(db) else "down",
        "counts": {"users": await db.users.count_documents({}), "documents": await db.documents.count_documents({}),
                   "conversations": await db.conversations.count_documents({}),
                   "active_subscriptions": await db.subscriptions.count_documents({"status": "active"})},
        "integrations": {
            "groq": {"configured": bool(s.groq_api_key), "model": s.groq_model, "live_verified": False},
            "embedding": {"provider": s.embedding_provider or None,
                          "configured": bool(s.embedding_provider) and (s.embedding_provider != "google" or bool(s.google_api_key))},
            "vector_store": {"provider": s.vector_store_provider or None},
            "razorpay": {"configured": s.razorpay_configured, "webhook_secret_set": bool(s.razorpay_webhook_secret)},
            "langfuse": langfuse_status(s)},
        "limits": {"max_agent_steps": s.max_agent_steps, "max_tool_calls": s.max_tool_calls,
                   "max_retries": s.max_retries, "workflow_token_budget": s.workflow_token_budget},
        "tools": [{k: v for k, v in t.items() if k != "args_schema"} for t in REGISTRY.describe()],
    }


@router.get("/traces")
async def traces(limit: int = Query(25, ge=1, le=100), _: dict = Depends(admin_user), db: Any = Depends(db_dep)):
    """Recent workflow traces: metadata only (no prompts, answers or user text). Newest first."""
    rows = await db.traces.find({}).sort("created_at", -1).to_list(limit)
    items = [{"trace_id": r.get("trace_id"), "workflow": r.get("workflow"), "latency_ms": r.get("latency_ms"),
              "tokens": r.get("tokens", {}).get("total", 0), "retries": r.get("retries", 0),
              "error_category": r.get("error_category"), "created_at": r["created_at"].isoformat(),
              "spans": [{"name": x.get("name"), "kind": x.get("kind"), "status": x.get("status"),
                         "duration_ms": x.get("duration_ms"), "result": x.get("result")} for x in r.get("spans", [])]}
             for r in rows]
    guard = {"refused_off_topic": 0, "refused_injection": 0}
    for it in items:
        for sp in it["spans"]:
            if sp["name"] == "guardrail:scope" and sp.get("result") == "off_topic":
                guard["refused_off_topic"] += 1
            if sp["name"] == "guardrail:scope" and sp.get("result") == "injection_blocked":
                guard["refused_injection"] += 1
    return {"items": items, "guardrails": guard}


@router.get("/integrations/langfuse")
async def langfuse(_: dict = Depends(admin_user), s: Settings = Depends(settings_dep)):
    return await verify_langfuse(s)


@router.get("/users")
async def users(limit: int = Query(25, ge=1, le=100), skip: int = Query(0, ge=0), _: dict = Depends(admin_user),
                db: Any = Depends(db_dep)):
    total = await db.users.count_documents({})
    rows = await db.users.find({}).sort("created_at", -1).skip(skip).to_list(limit)
    return {"total": total, "items": [{"id": str(u["_id"]), "email": u["email"], "role": u["role"],
                                      "plan_id": await effective_plan_id(db, str(u["_id"])),
                                      "created_at": u["created_at"], "disabled": bool(u.get("disabled"))} for u in rows]}


@router.get("/audit")
async def audit(limit: int = Query(50, ge=1, le=200), _: dict = Depends(admin_user), db: Any = Depends(db_dep)):
    rows = await db.audit_events.find({}).sort("created_at", -1).to_list(limit)
    return {"items": [{"type": r["type"], "tool": r.get("tool"), "status": r.get("status"),
                       "created_at": r["created_at"]} for r in rows]}
