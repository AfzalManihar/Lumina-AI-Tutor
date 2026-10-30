from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import current_user, db_dep, settings_dep, uid
from app.core.config import Settings
from app.memory.service import MemoryService
from app.schemas.common import MemoryCreate, MemoryUpdate

router = APIRouter(prefix="/memory", tags=["memory"])


def svc_dep(db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)) -> MemoryService:
    return MemoryService(db, s)


@router.get("")
async def list_memories(limit: int = Query(50, ge=1, le=100), skip: int = Query(0, ge=0),
                        user: dict = Depends(current_user), svc: MemoryService = Depends(svc_dep)):
    out = await svc.list(uid(user), limit, skip)
    out["enabled"] = await svc.enabled_for(user)
    return out


@router.post("", status_code=201)
async def create_memory(body: MemoryCreate, user: dict = Depends(current_user), svc: MemoryService = Depends(svc_dep)):
    return await svc.create(user, body.text, body.type, body.source, body.conversation_id)


@router.patch("/{mem_id}")
async def update_memory(mem_id: str, body: MemoryUpdate, user: dict = Depends(current_user),
                        svc: MemoryService = Depends(svc_dep)):
    return await svc.update(user, mem_id, body.text, body.type)


@router.delete("/{mem_id}", status_code=204)
async def delete_memory(mem_id: str, user: dict = Depends(current_user), svc: MemoryService = Depends(svc_dep)):
    await svc.delete(uid(user), mem_id)


@router.delete("", status_code=200)
async def delete_all(user: dict = Depends(current_user), svc: MemoryService = Depends(svc_dep)):
    return {"deleted": await svc.delete_all(uid(user))}
