from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from app.api.deps import current_user, db_dep, settings_dep, uid
from app.core.config import Settings
from app.core.errors import AppError
from app.rag.store import get_vector_store
from app.services.container import get_embedder_for
from app.services.documents import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def svc_dep(request: Request, db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)) -> DocumentService:
    return DocumentService(db, s, get_embedder_for(request), get_vector_store(s, db))


@router.post("", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), user: dict = Depends(current_user),
                 svc: DocumentService = Depends(svc_dep), s: Settings = Depends(settings_dep)):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > s.max_upload_bytes + 64 * 1024:
        raise AppError("File too large", code="file_too_large", status_code=413)
    data = await file.read(s.max_upload_bytes + 1)  # never read more than limit+1 bytes
    return await svc.upload(uid(user), file.filename or "document", file.content_type, data)


@router.get("")
async def list_documents(limit: int = Query(20, ge=1, le=100), skip: int = Query(0, ge=0),
                         user: dict = Depends(current_user), svc: DocumentService = Depends(svc_dep)):
    return await svc.list(uid(user), limit, skip)


@router.get("/{doc_id}")
async def get_document(doc_id: str, user: dict = Depends(current_user), svc: DocumentService = Depends(svc_dep)):
    return await svc.get(uid(user), doc_id)


@router.get("/{doc_id}/passages")
async def passages(doc_id: str, page: int | None = Query(None, ge=1), user: dict = Depends(current_user),
                   svc: DocumentService = Depends(svc_dep)):
    return {"items": await svc.passages(uid(user), doc_id, page)}


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, user: dict = Depends(current_user), svc: DocumentService = Depends(svc_dep)):
    await svc.delete(uid(user), doc_id)


@router.post("/{doc_id}/reindex")
async def reindex(doc_id: str, user: dict = Depends(current_user), svc: DocumentService = Depends(svc_dep)):
    return await svc.reindex(uid(user), doc_id)
