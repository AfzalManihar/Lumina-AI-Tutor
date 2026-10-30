"""Query understanding & routing. Deterministic rules first; an LLM classifier is used only when the
rules are not confident. Output is a typed RoutedTask."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

SYSTEM_WORDS = ("hi", "hello", "hey", "thanks", "thank you", "ok", "okay")


class RoutedTask(BaseModel):
    intent: Literal["chat", "doc_qa", "lesson", "quiz", "evaluate", "progress", "calculate", "study_plan", "clarify", "off_topic"]
    topic: str | None = None
    difficulty: Literal["beginner", "intermediate", "advanced"] = "beginner"
    num_questions: int = Field(default=5, ge=1, le=10)
    wants_documents: bool = False
    expression: str | None = None
    complex: bool = False
    confidence: float = 0.9
    clarification_question: str | None = None
    needs_llm_classification: bool = False
    reason: str = ""


_DIFF = [(r"\b(advanced|hard|difficult|expert)\b", "advanced"),
         (r"\b(intermediate|medium|moderate)\b", "intermediate"),
         (r"\b(beginner|easy|basic|simple|introductory|intro)\b", "beginner")]
_DOC_REF = re.compile(r"\b(my (?:uploaded )?(?:document|documents|notes|pdf|file|files|textbook|upload)|"
                      r"the (?:uploaded )?(?:document|pdf|file|notes|textbook)|according to (?:my|the) |"
                      r"in (?:my|the) (?:document|pdf|notes|file))\b", re.I)
_CALC = re.compile(r"^(?:calculate|compute|evaluate|what is|what's|solve)?\s*([0-9(][0-9+\-*/^().,%\s]*[0-9)])\s*\??$", re.I)
_TOPIC = [
    re.compile(r"\b(?:quiz|test|questions?|mcqs?|lesson|tutorial|explanation|plan|revision)\b.*?\b(?:about|on|for|covering|regarding)\s+(.+?)(?:\s+(?:at|for|with|in)\s+(?:a\s+)?(?:beginner|easy|intermediate|advanced|hard).*)?[.?!]?$", re.I),
    re.compile(r"\b(?:teach me|explain|learn|study|understand)\s+(?:about\s+)?(.+?)[.?!]?$", re.I),
]


def _topic(msg: str) -> str | None:
    for rx in _TOPIC:
        m = rx.search(msg.strip())
        if m:
            t = re.sub(r"\b(please|thanks|thank you)\b", "", m.group(1), flags=re.I)
            t = re.sub(r"\s+(?:at|in)\s+(?:a\s+)?(?:beginner|easy|intermediate|advanced|hard)\b.*$", "", t, flags=re.I)
            t = re.sub(r"\s+", " ", t).strip(" ,.;:?!\"'")
            if 2 <= len(t) <= 120:
                return t
    return None


def route(message: str, *, active_topic: str | None = None, has_documents: bool = False,
          doc_selected: bool = False, history_len: int = 0) -> RoutedTask:
    m = message.strip()
    low = m.lower()
    diff = next((d for rx, d in _DIFF if re.search(rx, low)), "beginner")
    nq = 5
    mq = re.search(r"\b(\d{1,2})\s*(?:questions?|mcqs?|problems?)\b", low)
    if mq:
        nq = max(1, min(10, int(mq.group(1))))
    wants_docs = doc_selected or bool(_DOC_REF.search(m))
    base = dict(difficulty=diff, num_questions=nq, wants_documents=wants_docs)

    mc = _CALC.match(m)
    if mc and re.search(r"[+\-*/^%]", mc.group(1)):
        return RoutedTask(intent="calculate", expression=mc.group(1).replace("^", "**").strip(), reason="arithmetic", **base)

    topic = _topic(m) or active_topic
    if re.search(r"\b(my progress|learning progress|how am i doing|study history|my scores?)\b", low):
        return RoutedTask(intent="progress", reason="progress keywords", **base)
    if re.search(r"\b(study plan|revision plan|learning plan|roadmap|schedule)\b", low):
        return RoutedTask(intent="study_plan", topic=topic, complex=True, reason="plan keywords", **base)
    if re.search(r"\b(quiz me|quiz|test me|practice questions?|mcqs?|multiple choice)\b", low):
        if not topic and not wants_docs:
            return RoutedTask(intent="clarify", reason="quiz without topic", confidence=0.9,
                              clarification_question="What topic should the quiz cover, and at what difficulty (beginner, intermediate or advanced)?", **base)
        compound = bool(re.search(r"\b(and then|and also|then)\b.*\b(lesson|explain|plan|summary|summar)", low))
        return RoutedTask(intent="quiz", topic=topic, complex=compound, reason="quiz keywords", **base)
    if re.search(r"\b(lesson|teach me|tutorial|walk me through|step[- ]by[- ]step (?:guide|lesson))\b", low):
        if not topic and not wants_docs:
            return RoutedTask(intent="clarify", reason="lesson without topic", confidence=0.9,
                              clarification_question="Which topic would you like a lesson on?", **base)
        return RoutedTask(intent="lesson", topic=topic, reason="lesson keywords", **base)
    if re.search(r"\b(check my answer|is my answer|evaluate my answer|grade my|am i correct|is this correct)\b", low):
        return RoutedTask(intent="evaluate", topic=topic, reason="evaluation keywords", **base)
    if wants_docs:
        return RoutedTask(intent="doc_qa", topic=topic, reason="document reference", **base)

    words = re.findall(r"[a-z0-9']+", low)
    if len(words) <= 2 and low.strip("!?. ") not in SYSTEM_WORDS and not active_topic and history_len == 0:
        return RoutedTask(intent="clarify", reason="too short to interpret", confidence=0.8,
                          clarification_question="Could you tell me a bit more? For example, a topic you want to learn or a question you have.", **base)
    explicit = bool(re.search(r"\b(explain|what is|what are|why|how (?:do|does|did|can|to)|define|difference between|compare)\b", low))
    return RoutedTask(intent="chat", topic=topic, confidence=0.85 if explicit else 0.45,
                      needs_llm_classification=not explicit and len(words) > 3,
                      reason="default tutoring", **base)
