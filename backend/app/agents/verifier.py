
"""Accuracy / Verification agent.

Checks citation validity, lexical support, numeric claims, and structure.
Lexical matching is a heuristic, not proof of factual correctness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.embeddings import stem, tokenize
from app.schemas.learning import TutorOut


# Supports [S1] and **[S1]**.
_CITE = re.compile(r"(?:\*\*)?\[(S\d+)\](?:\*\*)?")
_NUM = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
SUPPORT_THRESHOLD = 0.60


def content_tokens(text: str) -> list[str]:
    """Normalize words and exclude citation markers."""
    text = _CITE.sub(" ", text)
    return [
        stem(token)
        for token in tokenize(text)
        if not token.isdigit()
    ]


def sentences(text: str) -> list[str]:
    """Split text into non-empty sentence and line units."""
    return [
        part.strip()
        for part in _SENT.split(text)
        if part and part.strip()
    ]


def _is_structure(text: str) -> bool:
    """Identify headings, empty list markers, and citation-only fragments."""
    text = text.strip()
    if not text:
        return True

    without_citations = _CITE.sub("", text).strip()
    if not without_citations:
        return True

    if re.match(r"^#{1,6}\s+", text):
        return True

    if re.match(r"^[-*+]\s*$", text):
        return True

    return False


@dataclass
class Verification:
    passed: bool
    invalid_citations: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    structural_issues: list[str] = field(default_factory=list)
    support_score: float = 1.0
    uncited: bool = False

    def feedback(self) -> str:
        lines: list[str] = []

        if self.invalid_citations:
            lines.append(
                "Remove or fix citations not present in the sources: "
                + ", ".join(self.invalid_citations)
            )

        for sentence in self.unsupported[:5]:
            lines.append(
                f'Unsupported by the sources (verify or rewrite): '
                f'"{sentence[:200]}"'
            )

        for sentence in self.contradictions[:3]:
            lines.append(
                f'Possible numeric contradiction; check against sources: '
                f'"{sentence[:200]}"'
            )

        lines.extend(self.structural_issues)

        if self.uncited:
            lines.append(
                "Add inline [S#] citations for source-based factual claims."
            )

        return "\n".join(lines)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "invalid_citations": self.invalid_citations,
            "unsupported_count": len(self.unsupported),
            "contradiction_count": len(self.contradictions),
            "structural_issues": self.structural_issues,
            "support_score": round(self.support_score, 3),
            "uncited": self.uncited,
        }


def verify(
    out: TutorOut,
    hits: list[dict],
    grounded: bool,
) -> Verification:
    """Verify an answer against authorized retrieved evidence."""
    result = Verification(passed=True)
    answer = (out.answer or "").strip()

    if not answer:
        result.structural_issues.append("Answer is empty")

    if not grounded:
        result.passed = not result.structural_issues
        return result

    # Explicit abstentions contain no factual answer claims to verify.
    if out.cannot_answer:
        result.passed = not result.structural_issues
        return result

    valid_ids = {
        str(hit["cite_id"])
        for hit in hits
        if hit.get("cite_id")
    }

    inline_ids = set(_CITE.findall(answer))
    declared_ids = {
        str(citation).strip()
        for citation in (out.citations or [])
        if str(citation).strip()
    }
    referenced_ids = inline_ids | declared_ids

    result.invalid_citations = sorted(
        citation
        for citation in referenced_ids
        if citation not in valid_ids
    )

    good_ids = referenced_ids & valid_ids
    result.uncited = not bool(good_ids)

    by_id = {
        str(hit["cite_id"]): hit
        for hit in hits
        if hit.get("cite_id")
    }

    evidence_hits = (
        [by_id[citation] for citation in sorted(good_ids)]
        if good_ids
        else hits
    )

    evidence_text = " ".join(
        str(hit.get("text") or "")
        for hit in evidence_hits
    )
    evidence_tokens = set(content_tokens(evidence_text))
    evidence_numbers = set(_NUM.findall(evidence_text))

    evidence_sentences = [
        (
            sentence,
            set(content_tokens(sentence)),
            set(_NUM.findall(sentence)),
        )
        for hit in evidence_hits
        for sentence in sentences(str(hit.get("text") or ""))
    ]

    scores: list[float] = []

    for sentence in sentences(answer):
        if _is_structure(sentence):
            continue

        normalized = re.sub(
            r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s*)",
            "",
            sentence,
        ).strip()

        if not normalized or normalized.endswith("?"):
            continue

        tokens = content_tokens(normalized)

        # Short labels/fragments are unreliable for lexical scoring.
        if len(tokens) < 4:
            continue

        token_set = set(tokens)
        support = sum(
            1 for token in tokens if token in evidence_tokens
        ) / len(tokens)
        scores.append(support)

        numbers = set(_NUM.findall(normalized))

        if support < SUPPORT_THRESHOLD:
            result.unsupported.append(sentence)

        # Flag numeric claims containing values absent from the evidence.
        if numbers and not numbers.issubset(evidence_numbers):
            result.unsupported.append(sentence)

        # Heuristic for possible numeric contradictions.
        if numbers and evidence_sentences:
            best = max(
                evidence_sentences,
                key=lambda item: (
                    len(token_set & item[1]) / max(len(token_set), 1)
                ),
                default=None,
            )

            if best:
                _, source_tokens, source_numbers = best
                similarity = (
                    len(token_set & source_tokens)
                    / max(len(token_set), 1)
                )

                if (
                    similarity >= 0.5
                    and source_numbers
                    and numbers != source_numbers
                    and not numbers.issubset(source_numbers)
                ):
                    result.contradictions.append(sentence)

    result.unsupported = list(dict.fromkeys(result.unsupported))
    result.contradictions = list(dict.fromkeys(result.contradictions))

    result.support_score = (
        sum(scores) / len(scores) if scores else 1.0
    )

    result.passed = not (
        result.invalid_citations
        or result.unsupported
        or result.contradictions
        or result.structural_issues
        or result.uncited
    )

    return result


def supported_only(out: TutorOut, hits: list[dict]) -> str:
    """Remove unsupported sentences without inventing replacement claims."""
    answer = (out.answer or "").strip()
    if not answer:
        return ""

    verification = verify(out, hits, grounded=True)

    if not verification.unsupported:
        return answer

    unsupported = set(verification.unsupported)
    kept_lines: list[str] = []

    for line in answer.splitlines():
        if not line.strip():
            kept_lines.append("")
            continue

        # Preserve Markdown headings.
        if re.match(r"^\s*#{1,6}\s+", line):
            kept_lines.append(line)
            continue

        kept_parts = []

        for part in sentences(line):
            if part in unsupported:
                continue

            # Do not leave a citation-only fragment after filtering.
            if _is_structure(part):
                continue

            kept_parts.append(part)

        if kept_parts:
            kept_lines.append(" ".join(kept_parts))

    return "\n".join(kept_lines).strip()
