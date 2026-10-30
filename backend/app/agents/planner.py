"""Planning agent: decomposes complex learning requests into a bounded, validated list of subtasks."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.agents.router import RoutedTask
from app.core.errors import AppError

# Allowlisted subtask kinds and the tool (if any) each one needs.
SUBTASK_TOOLS = {"read_progress": "read_progress", "retrieve": "search_documents", "generate": None,
                 "quiz": "generate_quiz", "verify": None}


class Subtask(BaseModel):
    id: str
    kind: str
    depends_on: list[str] = Field(default_factory=list)
    optional: bool = False
    status: str = "pending"  # pending | done | failed | skipped


class Plan(BaseModel):
    subtasks: list[Subtask]
    replans: int = 0

    def get(self, sid: str) -> Subtask:
        return next(s for s in self.subtasks if s.id == sid)

    def ready(self) -> list[Subtask]:
        done = {s.id for s in self.subtasks if s.status in ("done", "skipped")}
        return [s for s in self.subtasks if s.status == "pending" and set(s.depends_on) <= done]

    def replan_after_failure(self, failed_id: str) -> bool:
        """Re-plan at most once: skip optional failed work and anything depending only on it."""
        failed = self.get(failed_id)
        if self.replans >= 1 or not failed.optional:
            return False
        failed.status = "skipped"
        self.replans += 1
        return True


def build_plan(task: RoutedTask, *, has_documents: bool, doc_grounded: bool) -> Plan:
    subs: list[Subtask] = []
    if task.intent == "study_plan":
        subs.append(Subtask(id="t1", kind="read_progress", optional=True))
        prev = ["t1"]
        if doc_grounded:
            subs.append(Subtask(id="t2", kind="retrieve", depends_on=[]))
            prev.append("t2")
        subs.append(Subtask(id="t3", kind="generate", depends_on=prev))
        if doc_grounded:
            subs.append(Subtask(id="t4", kind="verify", depends_on=["t3"]))
    elif task.intent == "quiz" and task.complex:
        subs.append(Subtask(id="t1", kind="generate"))
        subs.append(Subtask(id="t2", kind="quiz", depends_on=["t1"]))
    else:
        subs.append(Subtask(id="t1", kind="generate"))
    return Plan(subtasks=subs)


def validate_plan(plan: Plan, *, max_steps: int, max_tool_calls: int, allowed_tools: set[str]) -> None:
    ids = {s.id for s in plan.subtasks}
    if len(ids) != len(plan.subtasks):
        raise AppError("Plan has duplicate subtasks", code="invalid_plan", status_code=422)
    if len(plan.subtasks) > max_steps:
        raise AppError("Plan exceeds the step budget", code="invalid_plan", status_code=422)
    tool_calls = 0
    for s in plan.subtasks:
        if s.kind not in SUBTASK_TOOLS:
            raise AppError(f"Unknown subtask kind '{s.kind}'", code="invalid_plan", status_code=422)
        if not set(s.depends_on) <= ids:
            raise AppError("Plan references an unknown dependency", code="invalid_plan", status_code=422)
        tool = SUBTASK_TOOLS[s.kind]
        if tool:
            tool_calls += 1
            if tool not in allowed_tools:
                raise AppError(f"Tool '{tool}' not permitted for this plan", code="invalid_plan", status_code=403)
    if tool_calls > max_tool_calls:
        raise AppError("Plan exceeds the tool-call budget", code="invalid_plan", status_code=422)
    # cycle check (Kahn)
    deps = {s.id: set(s.depends_on) for s in plan.subtasks}
    resolved: set[str] = set()
    while deps:
        ready = [k for k, v in deps.items() if v <= resolved]
        if not ready:
            raise AppError("Plan contains a dependency cycle", code="invalid_plan", status_code=422)
        for k in ready:
            resolved.add(k)
            deps.pop(k)
