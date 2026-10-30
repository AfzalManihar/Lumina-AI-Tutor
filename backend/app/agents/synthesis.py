"""Response synthesis: builds the final student-facing answer from validated parts only."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agents.verifier import Verification, sentences, supported_only
from app.guardrails.output import scrub_output
from app.schemas.learning import TutorOut

_CITE = re.compile(r"\[(S\d+)\]")

NO_DOCUMENTS = ("You asked me to answer from your documents, but I couldn't find any ready documents to search. "
                "Upload a document first, or ask without document grounding for a general answer.")
NO_RELEVANT = ("I couldn't find relevant passages in your documents for that question, so I won't guess. "
               "Try rephrasing, selecting a different document, or ask without document grounding for a general answer.")
NOT_ENOUGH = ("Your documents don't contain enough information to answer this reliably, so I can't give a "
              "document-grounded answer.")


@dataclass
class Final:
    answer: str
    grounding_status: str  # grounded | insufficient_evidence | not_requested
    citations: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)


def _dedupe(text: str) -> str:
    out, seen = [], set()
    for para in re.split(r"\n{2,}", text):
        key = re.sub(r"\W+", " ", para).strip().lower()
        if key and key in seen:
            continue
        seen.add(key)
        out.append(para)
    return "\n\n".join(out)


def insufficient(status: str) -> Final:
    msg = NO_DOCUMENTS if status == "no_documents" else NO_RELEVANT
    return Final(msg, "insufficient_evidence", limitations=["No document evidence was available for this answer."])


def synthesize(out: TutorOut | None, verification: Verification | None, hits: list[dict], grounded: bool,
               secrets: list[str], max_chars: int, corrected: bool = False) -> Final:
    assert out is not None
    limits: list[str] = []
    text = out.answer
    if not grounded:
        text, flags = scrub_output(_dedupe(text), secrets, max_chars)
        if out.confidence == "low":
            limits.append("The tutor is not fully confident in this answer; please double-check important details.")
        return Final(text, "not_requested", [], limits, flags, out.follow_ups[:3])

    valid = {h["cite_id"] for h in hits}
    if out.cannot_answer:
        return Final(NOT_ENOUGH + ((" " + _first(out.answer)) if out.answer else ""), "insufficient_evidence",
                     limitations=["The model reported the sources were insufficient."])
    if verification and not verification.passed:
        kept = supported_only(out, hits)
        if len(kept.split()) < 5:
            return Final(NOT_ENOUGH, "insufficient_evidence",
                         limitations=["The draft could not be verified against your documents."],
                         flags=["unsupported_content_removed"])
        text = kept
        limits.append("Some statements could not be confirmed in your documents and were removed.")
    elif corrected:
        limits.append("The first draft was revised after verification.")
    text = _CITE.sub(lambda m: m.group(0) if m.group(1) in valid else "", text)
    used = [c for c in dict.fromkeys(_CITE.findall(text) + [c for c in out.citations]) if c in valid]
    text, flags = scrub_output(_dedupe(text), secrets, max_chars)
    if not used:
        limits.append("No citation could be attached to this answer; treat it with caution.")
    by_id = {h["cite_id"]: h for h in hits}
    cites = [{"cite_id": c, "chunk_id": by_id[c]["chunk_id"], "document_id": by_id[c]["document_id"],
              "filename": by_id[c]["filename"], "page": by_id[c]["page"], "section": by_id[c].get("section"),
              "passage": by_id[c]["text"], "score": round(float(by_id[c]["score"]), 4)} for c in used]
    return Final(text, "grounded" if cites else "insufficient_evidence", cites, limits, flags, out.follow_ups[:3])


def _first(text: str) -> str:
    s = sentences(text)
    return s[0][:300] if s else ""
