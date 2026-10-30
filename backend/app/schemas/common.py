from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.auth import StrictModel

MemoryType = Literal["preference", "goal", "topic", "progress_summary", "fact"]


class MemoryCreate(StrictModel):
    text: str = Field(min_length=3, max_length=500)
    type: MemoryType = "preference"
    source: Literal["user_manual", "approved_suggestion"] = "user_manual"
    conversation_id: str | None = Field(default=None, max_length=40)


class MemoryUpdate(StrictModel):
    text: str | None = Field(default=None, min_length=3, max_length=500)
    type: MemoryType | None = None
