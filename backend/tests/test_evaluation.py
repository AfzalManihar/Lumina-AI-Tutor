"""Evaluation framework tests: metric correctness, dataset integrity, reproducibility, detection of bad drafts."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from evaluation import metrics as M  # noqa: E402
from evaluation.run import DEFAULT_DATASET, evaluate  # noqa: E402

REQUIRED = {"answerable", "unanswerable", "irrelevant_documents", "ambiguous", "conflicting_evidence", "malformed",
            "prompt_injection_message", "prompt_injection_document", "verification"}


def test_dataset_is_versioned_synthetic_and_complete():
    ds = json.loads(DEFAULT_DATASET.read_text())
    assert ds["version"] and ds["synthetic"] is True and "NOT independently" in ds["label_provenance"]
    assert REQUIRED <= {c["category"] for c in ds["cases"]}
    ids = [c["id"] for c in ds["cases"]]
    assert len(ids) == len(set(ids))
    for c in ds["cases"]:
        if c["category"] == "answerable":
            assert c["expected_file"] and c["expected_page"] and c["reference_keywords"]
            assert any(ds["documents"][k]["filename"] == c["expected_file"] for k in c["docs"])


def test_metric_functions():
    hits = [{"filename": "a.pdf", "page": 1, "chunk_id": "1", "text": "t", "document_id": "d"},
            {"filename": "b.pdf", "page": 2, "chunk_id": "2", "text": "u", "document_id": "e"}]
    rel = [("a.pdf", 1), ("c.pdf", 3)]
    assert M.retrieval_hit(hits, rel) and not M.retrieval_hit(hits, [("z.pdf", 9)])
    assert M.context_precision(hits, rel) == 0.5 and M.context_recall(hits, rel) == 0.5
    assert M.context_precision([], rel) is None
    good = {"chunk_id": "1", "passage": "t", "page": 1, "document_id": "d", "filename": "a.pdf"}
    forged_text = {**good, "passage": "tampered"}
    forged_id = {**good, "chunk_id": "999"}
    assert M.citation_correctness([good], hits) == 1.0
    assert M.citation_correctness([good, forged_text, forged_id], hits) == round(1 / 3, 4)
    assert M.citation_correctness([], hits) is None
    assert M.reference_coverage("It is Chlorophyll", ["chlorophyll", "stroma"]) == 0.5
    p = M.prf([(True, True), (True, False), (False, False), (False, True)])
    assert (p["tp"], p["fp"], p["fn"], p["tn"], p["precision"], p["recall"]) == (1, 1, 1, 1, 0.5, 0.5)
    assert M.rate([]) is None and M.rate([True, False]) == 0.5


def test_full_run_is_reproducible_and_meaningful():
    ds = json.loads(DEFAULT_DATASET.read_text())
    a = asyncio.run(evaluate(ds))
    b = asyncio.run(evaluate(ds))
    volatile = {"avg_latency_ms"}
    strip = lambda m: {k: v for k, v in m.items() if k not in volatile}  # noqa: E731
    assert strip(a["metrics"]) == strip(b["metrics"])  # deterministic given the dataset
    m = a["metrics"]
    # regression floors on the synthetic set (not claims about production quality)
    assert m["retrieval_hit_rate"] >= 0.9 and m["citation_correctness_mean"] == 1.0
    assert m["unsupported_claim_detection"]["recall"] == 1.0 and m["false_positive_rate_on_supported_drafts"] == 0.0
    assert m["abstention_rate_on_unanswerable_and_irrelevant"] == 1.0 and m["secret_leak_rate"] == 0.0
    assert m["malformed_input_rejection_rate"] == 1.0 and m["invalid_tool_call_rejection_rate"] == 1.0
    assert a["informational"]["near_miss_abstention_rate"] is not None


def test_evaluation_would_detect_a_broken_pipeline(monkeypatch):
    """Sanity check that the metrics can fail: disable the verifier's unsupported-claim detection."""
    import app.agents.verifier as vf
    real = vf.verify

    def lenient(out, hits, grounded):
        v = real(out, hits, grounded)
        v.passed = True
        return v

    monkeypatch.setattr(vf, "verify", lenient)
    import evaluation.run as run
    monkeypatch.setattr("app.agents.verifier.verify", lenient)
    ds = json.loads(DEFAULT_DATASET.read_text())
    agg = asyncio.run(run.evaluate(ds))
    assert agg["metrics"]["unsupported_claim_detection"]["recall"] < 1.0


def test_cli_writes_result_files(tmp_path):
    from evaluation.run import main
    assert main(["--out", str(tmp_path), "--quiet"]) == 0
    data = json.loads((tmp_path / "latest.json").read_text())
    r = data["run"]
    assert r["dataset_version"] and r["workflow_version"] and r["live_provider_calls"] == 0 and "mock" in r["llm"]
    assert (tmp_path / "latest_cases.csv").exists()
