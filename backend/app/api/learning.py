"""Lessons, quizzes, answer evaluation, progress and the student dashboard."""
from __future__ import annotations

from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, Query, Request

from app.agents import assessment
from app.api.deps import current_user, db_dep, settings_dep, uid
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.security import utcnow
from app.guardrails.input import check_user_input
from app.guardrails.retrieval import validate_object_id
from app.memory.service import MemoryService
from app.schemas.learning import AnswerEvaluation, EvaluateAnswerIn, LessonIn, QuizIn, QuizSubmitIn
from app.services import learning as svc
from app.services.billing import BillingService
from app.services.container import get_lazy_retriever, get_llm_for
from app.services.conversations import ConversationService
from app.services.metering import metered
from app.services.usage import UsageService

router = APIRouter(tags=["learning"])


@router.post("/lessons", status_code=201)
async def create_lesson(body: LessonIn, request: Request, user: dict = Depends(current_user),
                        db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    check_user_input(body.topic + " " + (body.objective or ""), s.max_input_chars)
    memories = await MemoryService(db, s).relevant(user, body.topic)
    async with metered(db, s, get_llm_for(request), uid(user), "lesson", request.state.request_id) as (llm, trace):
        with trace.span("lesson_generate", "agent"):
            return await svc.create_lesson(db, s, llm, get_lazy_retriever(request), uid(user), body.topic,
                                           body.difficulty, body.objective, body.language, body.document_ids, memories)


@router.get("/lessons")
async def list_lessons(limit: int = Query(20, ge=1, le=100), skip: int = Query(0, ge=0),
                       user: dict = Depends(current_user), db: Any = Depends(db_dep)):
    total = await db.lessons.count_documents({"user_id": uid(user)})
    rows = await db.lessons.find({"user_id": uid(user)}).sort("created_at", -1).skip(skip).to_list(limit)
    return {"items": [{"id": str(r["_id"]), "topic": r["topic"], "difficulty": r["difficulty"],
                       "title": r["content"]["title"], "grounded": r.get("grounded", False),
                       "created_at": r["created_at"]} for r in rows], "total": total}


@router.get("/lessons/{lesson_id}")
async def get_lesson(lesson_id: str, user: dict = Depends(current_user), db: Any = Depends(db_dep)):
    validate_object_id(lesson_id, "lesson id")
    d = await db.lessons.find_one({"_id": ObjectId(lesson_id), "user_id": uid(user)})
    if not d:
        raise NotFoundError("Lesson not found")
    return svc.lesson_out(d)


@router.post("/quizzes", status_code=201)
async def create_quiz(body: QuizIn, request: Request, user: dict = Depends(current_user),
                      db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    check_user_input(body.topic, s.max_input_chars)
    async with metered(db, s, get_llm_for(request), uid(user), "quiz", request.state.request_id) as (llm, trace):
        with trace.span("quiz_generate", "agent"):
            return await svc.create_quiz(db, s, llm, get_lazy_retriever(request), uid(user), body.topic,
                                         body.difficulty, body.num_questions, body.document_ids)


@router.get("/quizzes")
async def list_quizzes(limit: int = Query(20, ge=1, le=100), skip: int = Query(0, ge=0),
                       user: dict = Depends(current_user), db: Any = Depends(db_dep)):
    total = await db.quizzes.count_documents({"user_id": uid(user)})
    rows = await db.quizzes.find({"user_id": uid(user)}).sort("created_at", -1).skip(skip).to_list(limit)
    return {"items": [{k: v for k, v in svc.quiz_public(r).items() if k != "questions"} | {"question_count": len(r["questions"])}
                      for r in rows], "total": total}


@router.get("/quizzes/{quiz_id}")
async def get_quiz(quiz_id: str, user: dict = Depends(current_user), db: Any = Depends(db_dep)):
    q = await svc.get_quiz(db, uid(user), quiz_id)
    return svc.quiz_public(q, reveal=bool(q.get("attempts")))  # answer key only after at least one attempt


@router.post("/quizzes/{quiz_id}/submit")
async def submit_quiz(quiz_id: str, body: QuizSubmitIn, user: dict = Depends(current_user), db: Any = Depends(db_dep)):
    return await svc.submit_quiz(db, uid(user), quiz_id, body.answers)


@router.post("/assessments/evaluate")
async def evaluate_answer(body: EvaluateAnswerIn, request: Request, user: dict = Depends(current_user),
                          db: Any = Depends(db_dep), s: Settings = Depends(settings_dep)):
    check_user_input(body.question, s.max_input_chars)
    if not body.answer.strip():  # deterministic, no metering needed
        return AnswerEvaluation(score=0.0, feedback="No answer was provided.", missing_points=[],
                                verdict="incorrect").model_dump()
    check_user_input(body.answer, s.max_input_chars)
    async with metered(db, s, get_llm_for(request), uid(user), "evaluate", request.state.request_id) as (llm, trace):
        with trace.span("evaluate_answer", "agent"):
            res = await assessment.evaluate_free_answer(llm, body.question, body.answer, body.reference)
    await db.learning_events.insert_one({
        "user_id": uid(user), "type": "answer_evaluation", "topic": body.topic or "general", "score": res.score,
        "created_at": utcnow()})
    return res.model_dump()


@router.get("/progress")
async def progress(user: dict = Depends(current_user), db: Any = Depends(db_dep)):
    return await svc.progress_summary(db, uid(user))


@router.get("/dashboard")
async def dashboard(request: Request, user: dict = Depends(current_user), db: Any = Depends(db_dep),
                    s: Settings = Depends(settings_dep)):
    """Everything is read from the database for the authenticated user; nothing is hardcoded."""
    u = uid(user)
    docs = await db.documents.find({"user_id": u}).sort("created_at", -1).to_list(5)
    quiz_events = await db.learning_events.find({"user_id": u, "type": "quiz_attempt"}).sort("created_at", -1).to_list(5)
    return {
        "recent_conversations": (await ConversationService(db, s).list(u, 5, 0))["items"],
        "progress": await svc.progress_summary(db, u),
        "documents": {"total": await db.documents.count_documents({"user_id": u}),
                      "recent": [{"id": str(d["_id"]), "filename": d["filename"], "status": d["status"],
                                  "created_at": d["created_at"]} for d in docs]},
        "recent_quiz_results": [{"topic": e["topic"], "percent": e["percent"], "score": e["score"],
                                 "total": e["total"], "created_at": e["created_at"]} for e in quiz_events],
        "subscription": await BillingService(db, s, request.app.state.razorpay).subscription(u),
        "usage": await UsageService(db, s).summary(u),
    }
