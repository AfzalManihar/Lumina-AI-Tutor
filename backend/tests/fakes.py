"""Deterministic fakes for provider clients (tests only)."""
from __future__ import annotations

import json
from typing import Any, Callable


class FakeLLM:
    """Scriptable LLM stand-in. Matches the LLMClient interface; never calls a network."""
    model = "openai/gpt-oss-120b"

    def __init__(self, responder: Callable[[list[dict], dict], str] | None = None):
        self.responder = responder
        self.calls: list[list[dict]] = []
        self.queue: list[Any] = []

    def push(self, *items: Any) -> None:
        self.queue.extend(items)

    async def chat(self, messages, *, max_tokens=None, json_mode=False, temperature=0.2):
        from app.agents.llm import LLMResult
        self.calls.append(messages)
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            text = item if isinstance(item, str) else json.dumps(item)
        elif self.responder:
            text = self.responder(messages, {"json_mode": json_mode})
        else:
            text = "Default tutor answer."
        n = max(1, len(text) // 4)
        return LLMResult(text=text, usage={"prompt": 50, "completion": n, "total": 50 + n}, model=self.model)


def smart_responder(messages: list[dict], opts: dict) -> str:
    """Scripted 'model' used by workflow tests. It behaves like a faithful tutor: grounded answers are
    extracted from the first source so they are genuinely supported; quiz/lesson JSON honours the request."""
    import re
    sysm = messages[0]["content"]
    last = messages[-1]["content"]
    if "assessment engine" in sysm:
        if "multiple-choice" in last:
            n = int(re.search(r"exactly (\d+) multiple-choice", last).group(1))
            diff = re.search(r"at (\w+) difficulty", last).group(1)
            topic = re.search(r'about "(.+?)" at', last).group(1)
            cites = re.findall(r"\[(S\d+)\] \(document", last)
            src = re.search(r"SOURCE_TEXT\n(.+?)\nSOURCE_TEXT", last, re.S)
            words = src.group(1).split()[:6] if src else []
            qs = []
            for i in range(n):
                prompt_txt = (" ".join(words) + f" question {i + 1}") if words else f"{topic} question number {i + 1}?"
                qs.append({"prompt": prompt_txt if words else prompt_txt, "options": [f"A{i}", f"B{i}", f"C{i}", f"D{i}"],
                           "correct_index": i % 4, "explanation": "Because it is the right option.",
                           "cite_ids": cites[:1] if cites else []})
            return json.dumps({"topic": topic, "difficulty": diff, "questions": qs})
        if "step-by-step lesson" in last:
            topic = re.search(r'lesson in .+? on "(.+?)" for a (\w+)', last)
            cites = re.findall(r"\[(S\d+)\] \(document", last)
            return json.dumps({"title": f"Intro to {topic.group(1)}", "topic": topic.group(1), "difficulty": topic.group(2),
                               "objectives": ["Understand the basics"],
                               "sections": [{"heading": "Basics", "content": "Here is the first section of the lesson."}],
                               "key_takeaways": ["Practice regularly"], "practice_questions": ["What is it?"],
                               "citations": cites[:1]})
        if "Evaluate the student's answer" in last:
            return json.dumps({"score": 0.8, "feedback": "Good answer, mostly complete.", "missing_points": [],
                               "verdict": "correct"})
    if "Classify the student's message" in sysm:
        return json.dumps({"intent": "chat", "topic": None, "confidence": 0.9})
    if "SOURCES:" in last:
        m = re.search(r"\[(S\d+)\].*?SOURCE_TEXT\n(.+?)\nSOURCE_TEXT", last, re.S)
        if m:
            first = re.split(r"(?<=[.!?])\s+", m.group(2).strip())[0]
            return json.dumps({"answer": f"{first} [{m.group(1)}]", "citations": [m.group(1)], "confidence": "high",
                               "cannot_answer": False, "follow_ups": ["Want a quiz on this?"]})
    return json.dumps({"answer": "Here is a clear step by step explanation of the concept you asked about.",
                       "citations": [], "confidence": "high", "cannot_answer": False, "follow_ups": []})
