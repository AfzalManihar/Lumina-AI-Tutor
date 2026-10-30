"""Output guardrails: secret-leak scrubbing, size limits, structured-output validation."""
from __future__ import annotations

import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.observability.tracing import redact

T = TypeVar("T", bound=BaseModel)

_PROMPT_LEAK = re.compile(r"(?i)(my|the) system prompt (is|says|reads)")


def scrub_output(text: str, secrets: list[str], max_chars: int) -> tuple[str, list[str]]:
    flags: list[str] = []
    cleaned = redact(text, secrets)
    if cleaned != text:
        flags.append("secret_redacted")
    if _PROMPT_LEAK.search(cleaned):
        flags.append("possible_prompt_leak")
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + " …"
        flags.append("truncated")
    return cleaned, flags


def parse_structured(raw: str, model: type[T]) -> T:
    """Parse JSON text into a validated model. Raises ValueError with a short, repair-friendly message."""
    import json
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.S)
    try:
        data = json.loads(txt)
    except ValueError as e:
        raise ValueError(f"Output is not valid JSON: {e}") from None
    try:
        return model.model_validate(data)
    except ValidationError as e:
        errs = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:6])
        raise ValueError(f"Output failed schema validation: {errs}") from None
