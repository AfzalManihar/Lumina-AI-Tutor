"""Typed workflow state and the explicit state machine (allowed transitions only)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import AppError


class S(str, Enum):
    START = "start"
    UNDERSTAND = "understand"
    CLARIFY = "clarify"
    PLAN = "plan"
    RETRIEVE = "retrieve"
    GENERATE = "generate"
    VERIFY = "verify"
    CORRECT = "correct"
    SYNTHESIZE = "synthesize"
    DONE = "done"
    FAILED = "failed"


TRANSITIONS: dict[S, set[S]] = {
    S.START: {S.UNDERSTAND},
    S.UNDERSTAND: {S.CLARIFY, S.DONE, S.PLAN, S.RETRIEVE, S.GENERATE, S.SYNTHESIZE, S.FAILED},
    S.CLARIFY: {S.DONE},
    S.PLAN: {S.RETRIEVE, S.GENERATE, S.FAILED},
    S.RETRIEVE: {S.GENERATE, S.SYNTHESIZE, S.FAILED},
    S.GENERATE: {S.VERIFY, S.SYNTHESIZE, S.FAILED},
    S.VERIFY: {S.CORRECT, S.SYNTHESIZE},
    S.CORRECT: {S.VERIFY, S.SYNTHESIZE, S.FAILED},
    S.SYNTHESIZE: {S.DONE},
    S.DONE: set(),
    S.FAILED: {S.SYNTHESIZE, S.DONE},
}

# States that consume the MAX_AGENT_STEPS budget (real work). UNDERSTAND/SYNTHESIZE/CLARIFY are
# deterministic bookkeeping and are free.
CHARGED = {S.PLAN, S.RETRIEVE, S.GENERATE, S.VERIFY, S.CORRECT}


class IllegalTransition(AppError):
    status_code = 500
    code = "illegal_transition"


class BudgetExhausted(AppError):
    status_code = 422
    code = "budget_exhausted"


class StepRecord(BaseModel):
    name: str
    status: str = "ok"
    detail: dict[str, Any] = Field(default_factory=dict)


class WorkflowState(BaseModel):
    state: S = S.START
    steps_used: int = 0
    tool_calls: int = 0
    correction_attempts: int = 0
    max_steps: int = 6
    max_tool_calls: int = 4
    history: list[StepRecord] = Field(default_factory=list)

    def can(self, nxt: S) -> bool:
        if nxt not in TRANSITIONS[self.state]:
            return False
        if nxt in CHARGED and self.steps_used >= self.max_steps:
            return False
        return True

    def go(self, nxt: S) -> None:
        if nxt not in TRANSITIONS[self.state]:
            raise IllegalTransition(f"Transition {self.state.value}->{nxt.value} is not allowed")
        if nxt in CHARGED:
            if self.steps_used >= self.max_steps:
                raise BudgetExhausted("Workflow step budget exhausted")
            self.steps_used += 1
        self.state = nxt

    def steps_left(self) -> int:
        return self.max_steps - self.steps_used

    def record(self, name: str, status: str = "ok", **detail: Any) -> None:
        self.history.append(StepRecord(name=name, status=status, detail=detail))
