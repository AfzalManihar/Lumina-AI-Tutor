"""Layered input guardrails. Heuristic detection is defence-in-depth, NOT a complete defence."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.core.errors import GuardrailError

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Patterns are intentionally conservative; they will miss paraphrased / obfuscated / multilingual attacks.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    r"disregard (all |any )?(the )?(previous|prior|above|earlier|system) (instructions|prompts?|rules)",
    r"forget (everything|all) (you|above|previous)",
    r"you are now (?:an? )?(?:unrestricted|jailbroken|dan\b)",
    r"(reveal|show|print|repeat|output) (me )?(your|the) (system|hidden|initial|developer) (prompt|instructions|message)",
    r"(system|developer) prompt",
    r"</?(system|assistant|developer)>",
    r"\bact as (?:if you (?:have|had) )?no (restrictions|rules|guidelines)",
    r"(save|store|remember) (this )?(to|in|into) (your |my )?(long[- ]term )?memory (silently|without (asking|telling))",
    r"override (the )?(safety|security|guardrails?)",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]

# Minimal, configurable content-safety rules (extend via SAFETY_RULES in code/config).
DEFAULT_SAFETY_RULES = [
    r"\b(how to|steps to|instructions to) (make|build|synthesi[sz]e) (a )?(bomb|explosive|nerve agent|bioweapon)\b",
    r"\bchild (sexual|porn)",
]
_SAFETY = [re.compile(p, re.I) for p in DEFAULT_SAFETY_RULES]

_SECRET_ASK = re.compile(r"(api[_ -]?key|password|secret|token)\s*(is|=|:)\s*\S{6,}", re.I)


@dataclass
class InputCheck:
    text: str
    injection_suspected: bool = False
    injection_blocked: bool = False  # clear attempt to override rules / extract the system prompt
    flags: list[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _CTRL.sub("", text)
    return text.strip()


# Broad pattern kept as a flag only: "what is a system prompt?" is a legitimate study question.
_FLAG_ONLY = {r"(system|developer) prompt"}


def detect_injection(text: str) -> list[str]:
    t = normalize_text(text)
    return [p.pattern for p in _INJ if p.search(t)]


def check_user_input(text: str, max_chars: int) -> InputCheck:
    if not isinstance(text, str) or not text.strip():
        raise GuardrailError("Message must not be empty", code="empty_input")
    if len(text) > max_chars:
        raise GuardrailError(f"Message exceeds {max_chars} characters", code="input_too_long")
    if _CTRL.search(text):
        raise GuardrailError("Message contains invalid control characters", code="malformed_input")
    clean = normalize_text(text)
    for p in _SAFETY:
        if p.search(clean):
            raise GuardrailError("This request cannot be processed by the tutor", code="content_policy")
    flags = []
    inj = detect_injection(clean)
    if inj:
        flags.append("prompt_injection_suspected")
    if _SECRET_ASK.search(clean):
        flags.append("contains_secret_like_text")
    blocked = any(p not in _FLAG_ONLY for p in inj)
    return InputCheck(text=clean, injection_suspected=bool(inj), injection_blocked=blocked, flags=flags)
