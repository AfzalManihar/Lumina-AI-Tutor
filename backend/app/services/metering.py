"""Usage metering around every LLM-backed workflow: reserve -> run -> settle/release."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.agents.llm import BudgetedLLM
from app.core.config import Settings
from app.core.errors import UsageLimitError
from app.observability.tracing import Trace
from app.services.usage import UsageService


@asynccontextmanager
async def metered(db: Any, settings: Settings, llm_inner: Any, user_id: str, feature: str,
                  request_id: str | None = None) -> AsyncIterator[tuple[BudgetedLLM, Trace]]:
    usage = UsageService(db, settings)
    want = settings.workflow_token_budget
    try:
        res = await usage.reserve(user_id, want)
    except UsageLimitError:
        res = await usage.reserve(user_id, settings.min_token_reserve)  # raises if even the minimum doesn't fit
    trace = Trace(feature, user_id, request_id)
    llm = BudgetedLLM(llm_inner, res["reserved"], trace, max_repairs=settings.max_retries)
    try:
        yield llm, trace
    except BaseException:
        if llm.used > 0:
            await usage.settle(user_id, res, llm.used, feature)  # tokens already spent are still billed
        else:
            await usage.release(user_id, res)
        await _store_trace(db, trace.emit())
        raise
    else:
        await usage.settle(user_id, res, llm.used, feature)
        await _store_trace(db, trace.emit())


async def _store_trace(db: Any, summary: dict) -> None:
    """Persist trace metadata (names, durations, counts, statuses; never prompts or answers) for the admin trace view.
    Observability must never break a request, so failures are swallowed."""
    from datetime import datetime, timezone
    try:
        await db.traces.insert_one({**summary, "created_at": datetime.now(timezone.utc)})
    except Exception:  # noqa: BLE001
        pass
