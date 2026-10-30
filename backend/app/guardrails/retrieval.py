"""Retrieval guardrails: isolate retrieved text from instructions and validate identifiers."""
from __future__ import annotations

import re

from bson import ObjectId

from app.core.errors import GuardrailError
from app.guardrails.input import detect_injection


def validate_object_id(value: str, what: str = "id") -> str:
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise GuardrailError(f"Invalid {what}", code="invalid_identifier")
    return value


def neutralize(text: str) -> str:
    """Strip role/markup tokens that could be read as structure by the model."""
    text = re.sub(r"</?\s*(system|assistant|developer|user|source|context)[^>]*>", "", text, flags=re.I)
    return text.replace("```", "'''")


def wrap_untrusted_sources(hits: list[dict]) -> str:
    """Return the evidence block. Delimiters + labelling tell the model this is DATA, not instructions."""
    if not hits:
        return "(no sources)"
    parts = []
    for h in hits:
        page = f", page {h['page']}" if h.get("page") else ""
        parts.append(f"[{h['cite_id']}] (document: {h.get('filename', 'unknown')}{page})\n"
                     f"<<<SOURCE_TEXT\n{neutralize(h['text'])}\nSOURCE_TEXT>>>")
    return "\n\n".join(parts)


def flag_injected_chunks(hits: list[dict]) -> list[str]:
    return [h["cite_id"] for h in hits if detect_injection(h["text"])]
