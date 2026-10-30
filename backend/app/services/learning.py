"""Lessons, quizzes, answer evaluation and progress - all scoped to the authenticated user."""
from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.agents import assessment
from app.agents.llm import BudgetedLLM
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.guardrails.input import detect_injection
from app.guardrails.retrieval import flag_injected_chunks, validate_object_id
from app.models.enums import ROLE_STUDENT


async def _grounding(retriever, user_id: str, topic: str, document_ids: list[str] | None) -> list[dict]:
    """Evidence for grounded generation. Raises when documents were requested but nothing relevant exists."""
    if document_ids is None:
        return []
    r = await retriever.retrieve(user_id, topic, document_ids, top_k=6)
    if r.status != "ok":
        raise AppError("No relevant content was found in the selected documents for this topic",
                       code="insufficient_evidence", status_code=422)
    bad = set(flag_injected_chunks(r.hits))
    return [h for h in r.hits if h["cite_id"] not in bad]


def quiz_public(q: dict, reveal: bool = False) -> dict:
    out = {"id": str(q["_id"]), "topic": q["topic"], "difficulty": q["difficulty"], "created_at": q["created_at"],
           "grounded": q.get("grounded", False), "attempts": len(q.get("attempts", [])),
           "questions": [{"prompt": x["prompt"], "options": x["options"], "cite_ids": x.get("cite_ids", []),
                          **({"correct_index": x["correct_index"], "explanation": x["explanation"]} if reveal else {})}
                         for x in q["questions"]]}
    if q.get("attempts"):
        last = q["attempts"][-1]
        out["last_attempt"] = {"score": last["score"], "total": last["total"], "percent": last["percent"],
                               "created_at": last["created_at"]}
    return out


async def create_quiz(db: Any, settings: Settings, llm: BudgetedLLM, retriever, user_id: str, topic: str,
                      difficulty: str, n: int, document_ids: list[str] | None = None) -> dict:
    hits = await _grounding(retriever, user_id, topic, document_ids)
    quiz = await assessment.generate_quiz(llm, topic, difficulty, n, hits)
    sources = {h["cite_id"]: {"document_id": h["document_id"], "filename": h["filename"], "page": h["page"]}
               for h in hits}
    doc = {"user_id": user_id, "topic": topic, "difficulty": difficulty, "grounded": bool(hits),
           "sources": sources, "questions": [q.model_dump() for q in quiz.questions], "attempts": [],
           "created_at": utcnow()}
    res = await db.quizzes.insert_one(doc)
    doc["_id"] = res.inserted_id
    return quiz_public(doc)


async def get_quiz(db: Any, user_id: str, quiz_id: str) -> dict:
    validate_object_id(quiz_id, "quiz id")
    q = await db.quizzes.find_one({"_id": ObjectId(quiz_id), "user_id": user_id})
    if not q:
        raise NotFoundError("Quiz not found")
    return q


async def submit_quiz(db: Any, user_id: str, quiz_id: str, answers: list[int]) -> dict:
    q = await get_quiz(db, user_id, quiz_id)
    if len(answers) != len(q["questions"]):
        raise AppError(f"Expected {len(q['questions'])} answers", code="invalid_answers", status_code=422)
    if any(a < 0 or a > 3 for a in answers):
        raise AppError("Answers must be option indexes 0-3", code="invalid_answers", status_code=422)
    graded = assessment.grade_quiz(q["questions"], answers)
    attempt = {"score": graded["score"], "total": graded["total"], "percent": graded["percent"],
               "answers": answers, "created_at": utcnow()}
    await db.quizzes.update_one({"_id": q["_id"], "user_id": user_id}, {"$push": {"attempts": attempt}})
    await db.learning_events.insert_one({
        "user_id": user_id, "type": "quiz_attempt", "topic": q["topic"], "difficulty": q["difficulty"],
        "quiz_id": quiz_id, "score": graded["score"], "total": graded["total"], "percent": graded["percent"],
        "created_at": utcnow()})
    return graded


async def create_lesson(db: Any, settings: Settings, llm: BudgetedLLM, retriever, user_id: str, topic: str,
                        difficulty: str, objective: str | None, language: str, document_ids: list[str] | None,
                        memories: list[dict] | None = None) -> dict:
    hits = await _grounding(retriever, user_id, topic, document_ids)
    lesson = await assessment.generate_lesson(llm, topic, difficulty, objective, hits, language, memories)
    by_id = {h["cite_id"]: h for h in hits}
    doc = {"user_id": user_id, "topic": topic, "difficulty": difficulty, "language": language,
           "grounded": bool(hits), "content": lesson.model_dump(),
           "sources": [{"cite_id": c, "filename": by_id[c]["filename"], "page": by_id[c]["page"],
                        "passage": by_id[c]["text"], "document_id": by_id[c]["document_id"]}
                       for c in lesson.citations if c in by_id],
           "created_at": utcnow()}
    res = await db.lessons.insert_one(doc)
    await db.learning_events.insert_one({"user_id": user_id, "type": "lesson", "topic": topic, "difficulty": difficulty,
                                         "lesson_id": str(res.inserted_id), "created_at": utcnow()})
    doc["_id"] = res.inserted_id
    return lesson_out(doc)


def lesson_out(d: dict) -> dict:
    return {"id": str(d["_id"]), "topic": d["topic"], "difficulty": d["difficulty"], "language": d.get("language"),
            "grounded": d.get("grounded", False), "created_at": d["created_at"], "lesson": d["content"],
            "sources": d.get("sources", [])}


async def progress_summary(db: Any, user_id: str) -> dict:
    events = await db.learning_events.find({"user_id": user_id}).sort("created_at", -1).to_list(500)
    topics: dict[str, dict] = {}
    quiz_pcts = []
    lessons = 0
    for e in events:
        t = topics.setdefault(e.get("topic", "general"), {"topic": e.get("topic", "general"), "lessons": 0,
                                                          "quiz_attempts": 0, "best_percent": None,
                                                          "last_activity": e["created_at"]})
        if e["type"] == "lesson":
            t["lessons"] += 1
            lessons += 1
        elif e["type"] == "quiz_attempt":
            t["quiz_attempts"] += 1
            quiz_pcts.append(e["percent"])
            t["best_percent"] = max(t["best_percent"] or 0, e["percent"])
    recent = [{"type": e["type"], "topic": e.get("topic"), "percent": e.get("percent"),
               "created_at": e["created_at"]} for e in events[:15]]
    return {"topics": sorted(topics.values(), key=lambda x: x["last_activity"], reverse=True),
            "quizzes_taken": len(quiz_pcts),
            "average_quiz_percent": round(sum(quiz_pcts) / len(quiz_pcts), 1) if quiz_pcts else None,
            "lessons_completed": lessons, "recent_activity": recent}


def progress_text(p: dict) -> str:
    if not p["topics"]:
        return ("You haven't completed any lessons or quizzes yet. Ask me for a lesson or a quiz on a topic to "
                "start tracking your progress.")
    lines = [f"You've completed {p['lessons_completed']} lesson(s) and {p['quizzes_taken']} quiz attempt(s)."]
    if p["average_quiz_percent"] is not None:
        lines.append(f"Your average quiz score is {p['average_quiz_percent']}%.")
    weak = [t for t in p["topics"] if t["best_percent"] is not None and t["best_percent"] < 60]
    if weak:
        lines.append("Topics worth revisiting: " + ", ".join(t["topic"] for t in weak) + ".")
    lines.append("Recent topics: " + ", ".join(t["topic"] for t in p["topics"][:5]) + ".")
    return " ".join(lines)
