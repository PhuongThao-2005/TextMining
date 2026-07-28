from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

from evaluation.e2e_runner import (
    BenchmarkRecord,
    aggregate_latency,
    records_from_rows,
    run_e2e_evaluation,
    write_e2e_artifacts,
)
from retrieval.schema import RetrievalResult


@dataclass(frozen=True)
class _Chunk:
    chunk_id: str = "c1"
    chunk_text: Any = "Nội dung căn cứ"
    citation_anchor: str = "Điều 1"
    citation_label: str = ""
    parent_unit_id: str = "p1"
    id_str: str = "d1"
    rerank_score: float = 0.9


class _FakeRetriever:
    def retrieve(self, question: str, *, filter_profile: str, top_n: int) -> RetrievalResult:
        del filter_profile, top_n
        if question == "retrieval fails":
            raise TimeoutError("api_key=super-secret retrieval timeout")
        chunk = _Chunk(chunk_text=object()) if question == "serialization fails" else _Chunk()
        return RetrievalResult(chunks=[chunk], total_candidates=1, filter_profile_used="broad")


class _FakeHybridRetriever:
    use_cross_encoder = False

    def retrieve_with_latency(self, question: str, **kwargs):
        del question, kwargs
        breakdown = SimpleNamespace(
            dense_latency_s=0.010,
            sparse_latency_s=0.020,
            fusion_latency_s=0.005,
            cross_encoder_latency_s=0.0,
            total_latency_s=0.035,
        )
        return RetrievalResult(chunks=[_Chunk()], total_candidates=1, filter_profile_used="broad"), breakdown


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "qa_id": "qa-1",
            "question": "success",
            "reference_answer": "Đáp án",
            "answer_type": "extractive",
            "category": "contract",
            "difficulty": "easy",
            "ground_truth": {"chunk_ids": ["c1"]},
        },
        {
            "qa_id": "qa-2",
            "question": "generation fails",
            "reference_answer": "Đáp án",
            "answer_type": "extractive",
            "category": "contract",
            "difficulty": "hard",
            "ground_truth": {"chunk_ids": ["c1"]},
        },
        {
            "qa_id": "qa-3",
            "question": "success after failure",
            "reference_answer": "Đáp án",
            "answer_type": "extractive",
            "category": "citation",
            "difficulty": "hard",
            "ground_truth": {"chunk_ids": ["c1"]},
        },
    ]


def _generator(qa: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
    assert context
    assert chunks
    if qa["question"] == "generation fails":
        raise ConnectionError("Bearer sensitive-token")
    return str(qa["reference_answer"])


def test_case_failure_continues_and_denominators_exclude_failed_cases() -> None:
    result = run_e2e_evaluation(
        records_from_rows(_rows()),
        retriever=_FakeRetriever(),
        generator=_generator,
        retrieval_top_k=5,
        filter_profile="broad",
        sensitive_values=["sensitive-token"],
    )

    assert [row["status"] for row in result.predictions] == ["success", "failed", "success"]
    assert result.counts == {
        "total_input": 3,
        "successful": 2,
        "failed": 1,
        "skipped": 0,
        "evaluated": 2,
    }
    assert result.metrics["overall"]["count"] == 2
    assert result.predictions[2]["qa_id"] == "qa-3"
    assert result.errors[0]["stage"] == "generation"
    assert "sensitive-token" not in json.dumps(result.errors)
    assert result.latency["stages"]["dense_retrieval"]["count"] == 3
    assert result.latency["stages"]["generation"]["count"] == 2
    assert result.latency["stages"]["total"]["count"] == 3


def test_retrieval_judge_serialization_and_parse_failures_are_isolated() -> None:
    rows = [
        BenchmarkRecord(index=1, row=None, parse_error=ValueError("bad json"), raw_excerpt="{"),
        BenchmarkRecord(index=2, row={**_rows()[0], "qa_id": "retrieval", "question": "retrieval fails"}),
        BenchmarkRecord(index=3, row={**_rows()[0], "qa_id": "judge", "question": "judge fails"}),
        BenchmarkRecord(index=4, row={**_rows()[0], "qa_id": "serialize", "question": "serialization fails"}),
        BenchmarkRecord(index=5, row={**_rows()[0], "qa_id": "final", "question": "success"}),
    ]

    def judge(qa: dict[str, Any], reference: str, predicted: str, context: str) -> dict[str, Any]:
        del reference, predicted, context
        if qa["question"] == "judge fails":
            raise RuntimeError("judge unavailable")
        return {"correctness": 1, "faithfulness": 1, "answer_relevancy": 1}

    result = run_e2e_evaluation(
        rows,
        retriever=_FakeRetriever(),
        generator=_generator,
        judge=judge,
        retrieval_top_k=5,
        filter_profile="broad",
    )

    assert [error["stage"] for error in result.errors] == [
        "benchmark_parsing",
        "retrieval",
        "judge",
        "serialization",
    ]
    assert result.predictions[-1]["status"] == "success"
    assert result.counts["successful"] == 1
    assert result.counts["failed"] == 4


def test_artifacts_and_report_include_difficulty_latency_and_failures(tmp_path: Path) -> None:
    result = run_e2e_evaluation(
        records_from_rows(_rows()),
        retriever=_FakeRetriever(),
        generator=_generator,
        retrieval_top_k=5,
        filter_profile="broad",
        qa_path="fixture.jsonl",
        config={"generation": {"model": "fake"}, "retrieval": {"top_k": 5}},
    )

    paths = write_e2e_artifacts(tmp_path, result)

    assert set(paths) == {"predictions", "metrics", "latency", "errors", "report"}
    assert len((tmp_path / "e2e_predictions.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    assert len((tmp_path / "errors.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## By Difficulty" in report
    assert "## Stage Latency" in report
    assert "## Failures" in report
    metrics = json.loads((tmp_path / "e2e_metrics.json").read_text(encoding="utf-8"))
    latency = json.loads((tmp_path / "latency.json").read_text(encoding="utf-8"))
    assert metrics["counts"]["evaluated"] == 2
    assert latency["counts"] == metrics["counts"]


def test_latency_aggregation_uses_only_recorded_stage_values() -> None:
    summary = aggregate_latency(
        [
            {"latency_ms": {"dense_retrieval": 10.0, "total": 20.0}},
            {"latency_ms": {"dense_retrieval": 30.0, "total": 40.0}},
            {"latency_ms": {"dense_retrieval": None, "total": 100.0}},
        ]
    )

    assert summary["stages"]["dense_retrieval"] == {
        "count": 2,
        "mean": 20.0,
        "median": 20.0,
        "min": 10.0,
        "max": 30.0,
        "p95": 30.0,
    }
    assert summary["stages"]["total"]["count"] == 3
    assert summary["stages"]["sparse_retrieval"] is None


def test_hybrid_breakdown_keeps_disabled_reranker_null() -> None:
    result = run_e2e_evaluation(
        records_from_rows([_rows()[0]]),
        retriever=_FakeHybridRetriever(),
        generator=_generator,
        retrieval_top_k=5,
        filter_profile="broad",
    )

    latency = result.predictions[0]["latency_ms"]
    assert latency["dense_retrieval"] == 10.0
    assert latency["sparse_retrieval"] == 20.0
    assert latency["fusion"] == 5.0
    assert latency["reranker"] is None
