from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.auth import StrictModel

Difficulty = Literal["beginner", "intermediate", "advanced"]
Intent = Literal["refused", "chat", "doc_qa", "lesson", "quiz", "evaluate", "progress", "calculate", "study_plan", "clarify", "off_topic"]


# ---- request models -------------------------------------------------------------------------
class ChatIn(StrictModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=40)
    document_ids: list[str] | None = Field(default=None, max_length=20)
    use_documents: bool = False
    topic: str | None = Field(default=None, max_length=120)


class LessonIn(StrictModel):
    topic: str = Field(min_length=2, max_length=120)
    difficulty: Difficulty = "beginner"
    objective: str | None = Field(default=None, max_length=300)
    language: str = Field(default="English", max_length=40)
    document_ids: list[str] | None = Field(default=None, max_length=20)


class QuizIn(StrictModel):
    topic: str = Field(min_length=2, max_length=120)
    difficulty: Difficulty = "beginner"
    num_questions: int = Field(default=5, ge=1, le=10)
    document_ids: list[str] | None = Field(default=None, max_length=20)


class QuizSubmitIn(StrictModel):
    answers: list[int] = Field(min_length=1, max_length=10)


class EvaluateAnswerIn(StrictModel):
    question: str = Field(min_length=3, max_length=1000)
    answer: str = Field(min_length=0, max_length=3000)
    reference: str | None = Field(default=None, max_length=2000)
    topic: str | None = Field(default=None, max_length=120)


# ---- LLM output schemas (validated) ---------------------------------------------------------
class TutorOut(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    citations: list[str] = Field(default_factory=list, max_length=12)
    confidence: Literal["high", "medium", "low"] = "medium"
    cannot_answer: bool = False
    follow_ups: list[str] = Field(default_factory=list, max_length=3)


class QuizQuestion(BaseModel):
    prompt: str = Field(min_length=5, max_length=500)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=3, max_length=800)
    cite_ids: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("options")
    @classmethod
    def _distinct(cls, v: list[str]) -> list[str]:
        if len({o.strip().lower() for o in v}) != 4 or any(not o.strip() for o in v):
            raise ValueError("options must be 4 distinct non-empty strings")
        return v


class GeneratedQuiz(BaseModel):
    topic: str
    difficulty: Difficulty
    questions: list[QuizQuestion] = Field(min_length=1, max_length=10)


class LessonSection(BaseModel):
    heading: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=10, max_length=4000)


class GeneratedLesson(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    topic: str
    difficulty: Difficulty
    objectives: list[str] = Field(min_length=1, max_length=6)
    sections: list[LessonSection] = Field(min_length=1, max_length=8)
    key_takeaways: list[str] = Field(min_length=1, max_length=8)
    practice_questions: list[str] = Field(default_factory=list, max_length=6)
    citations: list[str] = Field(default_factory=list, max_length=12)


class AnswerEvaluation(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(min_length=3, max_length=1500)
    missing_points: list[str] = Field(default_factory=list, max_length=6)
    verdict: Literal["correct", "partially_correct", "incorrect"]

    @model_validator(mode="after")
    def _consistent(self):
        if self.verdict == "correct" and self.score < 0.7:
            raise ValueError("verdict 'correct' requires score >= 0.7")
        if self.verdict == "incorrect" and self.score > 0.4:
            raise ValueError("verdict 'incorrect' requires score <= 0.4")
        return self


class IntentClassification(BaseModel):
    intent: Intent
    topic: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
