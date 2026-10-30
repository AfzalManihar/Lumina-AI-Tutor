"""Deterministic evaluation metrics. Pure functions: no I/O, no network, no randomness."""
from __future__ import annotations

import re
from typing import Iterable, Sequence

_TOK = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an the of and or to in on for with is are was were be by as at it this that from what who when where which how does do did".split())


def toks(text: str) -> set[str]:
    return {t for t in _TOK.findall(text.lower()) if t not in _STOP and len(t) > 1}


def safe_div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def mean(xs: Iterable[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


# ---- retrieval ------------------------------------------------------------------------------
def is_relevant(hit: dict, relevant: Sequence[tuple[str, int]]) -> bool:
    return any(hit.get("filename") == f and hit.get("page") == p for f, p in relevant)


def retrieval_hit(hits: Sequence[dict], relevant: Sequence[tuple[str, int]]) -> bool:
    """True when at least one labelled relevant (file, page) is among the retrieved chunks."""
    return any(is_relevant(h, relevant) for h in hits)


def context_precision(hits: Sequence[dict], relevant: Sequence[tuple[str, int]]) -> float | None:
    return safe_div(sum(is_relevant(h, relevant) for h in hits), len(hits))


def context_recall(hits: Sequence[dict], relevant: Sequence[tuple[str, int]]) -> float | None:
    found = {(f, p) for f, p in relevant if any(h.get("filename") == f and h.get("page") == p for h in hits)}
    return safe_div(len(found), len(set(map(tuple, relevant))))


# ---- citations / grounding ------------------------------------------------------------------
def citation_correctness(citations: Sequence[dict], retrieved: Sequence[dict], relevant: Sequence[tuple[str, int]] | None = None) -> float | None:
    """Share of emitted citations that (a) map to a chunk that was actually retrieved with identical text/page and
    (b) when labels exist, point at a labelled relevant source."""
    if not citations:
        return None
    by_chunk = {h["chunk_id"]: h for h in retrieved}
    ok = 0
    for c in citations:
        h = by_chunk.get(c.get("chunk_id"))
        good = bool(h) and h["text"] == c.get("passage") and h.get("page") == c.get("page") and h.get("document_id") == c.get("document_id")
        if good and relevant is not None:
            good = is_relevant(c, relevant)
        ok += good
    return round(ok / len(citations), 4)


def reference_coverage(answer: str, keywords: Sequence[str]) -> float | None:
    """Correctness proxy against a reference answer: fraction of reference keywords present in the answer."""
    a = answer.lower()
    return safe_div(sum(k.lower() in a for k in keywords), len(keywords))


def answer_relevance(answer: str, question: str) -> float | None:
    """Lexical relevance proxy: share of question content tokens that appear in the answer."""
    q = toks(question)
    return safe_div(len(q & toks(answer)), len(q))


# ---- classification-style ---------------------------------------------------------------------
def prf(pairs: Sequence[tuple[bool, bool]]) -> dict:
    """pairs of (label_positive, predicted_positive)."""
    tp = sum(1 for l, p in pairs if l and p)
    fp = sum(1 for l, p in pairs if not l and p)
    fn = sum(1 for l, p in pairs if l and not p)
    tn = sum(1 for l, p in pairs if not l and not p)
    prec, rec = safe_div(tp, tp + fp), safe_div(tp, tp + fn)
    f1 = round(2 * prec * rec / (prec + rec), 4) if prec and rec else (0.0 if prec is not None or rec is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec, "f1": f1,
            "accuracy": safe_div(tp + tn, len(pairs))}


def rate(flags: Sequence[bool]) -> float | None:
    return safe_div(sum(bool(f) for f in flags), len(flags))
