from __future__ import annotations

import json
import math
import re
import statistics
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

from generation.citations import aggregate_citation_metrics, prepare_citation_sources, validate_answer_citations
from generation.reasoning_client import (
    RawGenerationResponse, format_context_for_prompt, parse_generation_response,
)

from .io_utils import qa_id, write_json, write_jsonl
from .metrics import aggregate, aggregate_by, exact_match, is_unanswerable_text, rouge_l, token_f1


METRIC_KEYS = ["exact_match", "token_f1", "rouge_l", "unanswerable_accuracy", "context_recall@k"]
LATENCY_STAGES = [
    "dense_retrieval",
    "sparse_retrieval",
    "graph_traversal",
    "fusion",
    "reranker",
    "generation",
    "planner_decision",
    "tool_retrieval",
    "agent_total",
    "judge",
    "serialization",
    "total",
]
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|authorization|token|secret)(\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
)


GeneratorFunction = Callable[[dict[str, Any], str, Sequence[Any]], str]
JudgeFunction = Callable[[dict[str, Any], str, str, str], dict[str, Any]]
CaseExecutor = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class BenchmarkRecord:
    index: int
    row: dict[str, Any] | None
    parse_error: Exception | None = None
    raw_excerpt: str | None = None


@dataclass(frozen=True)
class E2ERunResult:
    predictions: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    metrics: dict[str, Any]
    latency: dict[str, Any]

    @property
    def counts(self) -> dict[str, int]:
        return dict(self.metrics["counts"])


def read_benchmark_records(path: Path, *, limit: int | None = None) -> Iterator[BenchmarkRecord]:
    emitted = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if limit is not None and emitted >= limit:
                break
            emitted += 1
            try:
                parsed = json.loads(stripped)
                if not isinstance(parsed, dict):
                    raise TypeError("Benchmark JSONL rows must be JSON objects.")
                yield BenchmarkRecord(index=line_no, row=parsed)
            except (json.JSONDecodeError, TypeError) as exc:
                yield BenchmarkRecord(
                    index=line_no,
                    row=None,
                    parse_error=exc,
                    raw_excerpt=stripped[:200],
                )


def records_from_rows(rows: Iterable[dict[str, Any]]) -> Iterator[BenchmarkRecord]:
    for index, row in enumerate(rows, start=1):
        yield BenchmarkRecord(index=index, row=row)


def run_e2e_evaluation(
    records: Iterable[BenchmarkRecord],
    *,
    retriever: Any,
    generator: GeneratorFunction,
    retrieval_top_k: int,
    filter_profile: str,
    judge: JudgeFunction | None = None,
    config: dict[str, Any] | None = None,
    qa_path: str | None = None,
    sensitive_values: Sequence[str] = (),
    case_executor: CaseExecutor | None = None,
) -> E2ERunResult:
    predictions: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for record in records:
        case_started = time.perf_counter()
        stage_latencies = _empty_latency()
        row = record.row
        case_identifier = qa_id(row or {}, record.index)
        current_stage = "benchmark_parsing"
        agent_payload: dict[str, Any] = {}

        if record.parse_error is not None:
            error_record = _error_record(
                case_identifier=case_identifier,
                stage=current_stage,
                exc=record.parse_error,
                sensitive_values=sensitive_values,
                details={"line_number": record.index, "raw_excerpt": record.raw_excerpt},
            )
            stage_latencies["total"] = _elapsed_ms(case_started)
            predictions.append(
                _failed_prediction(
                    case_identifier=case_identifier,
                    qa=None,
                    failed_stage=current_stage,
                    error_record=error_record,
                    latency=stage_latencies,
                )
            )
            errors.append(error_record)
            continue

        assert row is not None
        try:
            question = str(row.get("question") or "").strip()
            if not question and case_executor is None:
                stage_latencies["total"] = _elapsed_ms(case_started)
                predictions.append(
                    {
                        "qa_id": case_identifier,
                        "question": row.get("question"),
                        "category": row.get("category"),
                        "difficulty": row.get("difficulty"),
                        "answer_type": row.get("answer_type"),
                        "status": "skipped",
                        "skip_reason": "empty_question",
                        "latency_ms": stage_latencies,
                    }
                )
                continue

            if case_executor is not None:
                current_stage = "agent_execution"
                execution = case_executor(row)
                stage_latencies.update(getattr(execution, "latency_ms", {}) or {})
                status_value = getattr(getattr(execution, "status", None), "value", getattr(execution, "status", None))
                agent_payload = {
                    "agent_status": status_value,
                    "agent_reason_code": getattr(execution, "reason_code", None),
                    "agent_trace": execution.trace_dicts() if hasattr(execution, "trace_dicts") else [],
                    "retrieval_invoked": bool(getattr(execution, "retrieval_invoked", False)),
                    "tool_call_count": int(getattr(execution, "tool_call_count", 0)),
                    "successful_tool_calls": int(getattr(execution, "successful_tool_calls", 0)),
                }
                chunks = list(getattr(execution, "retrieved_items", ()) or ())
                context = format_context(chunks)
                if status_value == "abstained":
                    stage_latencies["total"] = _elapsed_ms(case_started)
                    predictions.append(_json_safe({
                        "qa_id": case_identifier, "question": row.get("question"),
                        "category": row.get("category"), "difficulty": row.get("difficulty"),
                        "answer_type": row.get("answer_type"), "status": "skipped",
                        "skip_reason": getattr(execution, "reason_code", None) or "agent_abstained",
                        "retrieved_context": [_chunk_to_dict(chunk, rank) for rank, chunk in enumerate(chunks, 1)],
                        **agent_payload, "latency_ms": stage_latencies,
                    }))
                    continue
                if status_value != "completed":
                    raise RuntimeError(
                        f"{getattr(execution, 'error_type', None) or 'AgentFailure'}: "
                        f"{getattr(execution, 'error_message', None) or getattr(execution, 'reason_code', None) or 'agent failed'}"
                    )
                predicted = str(getattr(execution, "final_answer", ""))
            else:
                current_stage = "retrieval"
                result, retrieval_latency = _retrieve_with_latency(
                    retriever, question, filter_profile=filter_profile, top_k=retrieval_top_k,
                )
                stage_latencies.update(retrieval_latency)
                chunks = list(result.chunks)
                context = format_context(chunks)
                agent_payload = {
                    "agent_status": "completed", "retrieval_invoked": True,
                    "tool_call_count": 0, "successful_tool_calls": 0,
                }
                if not chunks:
                    stage_latencies["total"] = _elapsed_ms(case_started)
                    predictions.append(_json_safe({
                        "qa_id": case_identifier, "question": row.get("question"),
                        "category": row.get("category"), "difficulty": row.get("difficulty"),
                        "answer_type": row.get("answer_type"), "status": "skipped",
                        "skip_reason": "empty_context", "retrieved_context": [],
                        "citations": [], "citation_references": [], "citation_warnings": [],
                        "citation_metrics": None, "invalid_citation_ids": [],
                        **agent_payload, "latency_ms": stage_latencies,
                    }))
                    continue
                current_stage = "generation"
                generation_started = time.perf_counter()
                predicted = generator(row, context, chunks)
                stage_latencies["generation"] = _elapsed_ms(generation_started)
            if not chunks:
                stage_latencies["total"] = _elapsed_ms(case_started)
                predictions.append(_json_safe({
                    "qa_id": case_identifier, "question": row.get("question"),
                    "category": row.get("category"), "difficulty": row.get("difficulty"),
                    "answer_type": row.get("answer_type"), "status": "skipped",
                    "skip_reason": "empty_context", "retrieved_context": [],
                    "citations": [], "citation_references": [], "citation_warnings": [],
                    "citation_metrics": None, "invalid_citation_ids": [],
                    **agent_payload, "latency_ms": stage_latencies,
                }))
                continue
            sources = prepare_citation_sources(chunks)
            safe_answer = parse_generation_response(
                RawGenerationResponse(str(predicted), None)
            ).answer
            citation_result = validate_answer_citations(safe_answer, sources)
            predicted = citation_result.answer
            reference_answer = str(row.get("reference_answer") or row.get("answer") or "")

            current_stage = "metrics"
            scored = score_case(row, record.index, predicted, reference_answer, chunks)

            current_stage = "judge"
            if judge is not None:
                judge_started = time.perf_counter()
                judged = judge(row, reference_answer, predicted, context)
                stage_latencies["judge"] = _elapsed_ms(judge_started)
                scored["llm_judge"] = judged
                scored["judge_correctness"] = float(judged.get("correctness") or 0.0)
                scored["judge_faithfulness"] = float(judged.get("faithfulness") or 0.0)
                scored["judge_answer_relevancy"] = float(judged.get("answer_relevancy") or 0.0)

            current_stage = "serialization"
            serialization_started = time.perf_counter()
            scored["retrieved_context"] = [_chunk_to_dict(chunk, rank) for rank, chunk in enumerate(chunks, start=1)]
            scored["citations"] = [source.to_dict(include_text=False) for source in citation_result.cited_sources]
            scored["citation_references"] = [vars(reference) for reference in citation_result.references]
            scored["citation_metrics"] = citation_result.metrics
            scored["citation_warnings"] = list(citation_result.warnings)
            scored["invalid_citation_ids"] = list(citation_result.invalid_ids)
            scored["status"] = "success"
            scored["failed_stage"] = None
            scored["error"] = None
            scored.update(agent_payload)
            stage_latencies["serialization"] = _elapsed_ms(serialization_started)
            stage_latencies["total"] = _elapsed_ms(case_started)
            scored["latency_ms"] = stage_latencies
            predictions.append(_json_safe(scored))
        except Exception as exc:
            stage_latencies["total"] = _elapsed_ms(case_started)
            error_record = _error_record(
                case_identifier=case_identifier,
                stage=current_stage,
                exc=exc,
                sensitive_values=sensitive_values,
            )
            failed_prediction = _failed_prediction(
                    case_identifier=case_identifier,
                    qa=row,
                    failed_stage=current_stage,
                    error_record=error_record,
                    latency=stage_latencies,
                )
            failed_prediction.update(agent_payload)
            if current_stage == "agent_execution":
                failed_prediction["agent_status"] = "failed"
            predictions.append(failed_prediction)
            errors.append(error_record)

    successful = [row for row in predictions if row["status"] == "success"]
    failed = [row for row in predictions if row["status"] == "failed"]
    skipped = [row for row in predictions if row["status"] == "skipped"]
    metric_keys = list(METRIC_KEYS)
    if successful and "judge_correctness" in successful[0]:
        metric_keys.extend(["judge_correctness", "judge_faithfulness", "judge_answer_relevancy"])
    counts = {
        "total_input": len(predictions),
        "successful": len(successful),
        "failed": len(failed),
        "skipped": len(skipped),
        "evaluated": len(successful),
    }
    metrics = {
        "qa_path": qa_path,
        "config": config or {},
        "counts": counts,
        "metric_denominator": "successful cases only",
        "overall": aggregate(successful, metric_keys),
        "by_category": aggregate_by(successful, "category", metric_keys),
        "by_answer_type": aggregate_by(successful, "answer_type", metric_keys),
        "by_difficulty": aggregate_by(successful, "difficulty", metric_keys),
        "metric_keys": metric_keys,
        "agent_metrics": aggregate_agent_metrics(predictions),
        "citation_metrics": aggregate_citation_metrics(successful),
    }
    latency = aggregate_latency(predictions)
    latency["denominator"] = (
        "Each stage uses cases with a recorded value for that stage; total includes successful, failed, and skipped cases."
    )
    latency["counts"] = counts
    return E2ERunResult(predictions=predictions, errors=errors, metrics=metrics, latency=latency)


def write_e2e_artifacts(
    out_dir: Path,
    result: E2ERunResult,
    *,
    report_name: str = "report.md",
) -> dict[str, str]:
    paths = {
        "predictions": out_dir / "e2e_predictions.jsonl",
        "metrics": out_dir / "e2e_metrics.json",
        "latency": out_dir / "latency.json",
        "errors": out_dir / "errors.jsonl",
        "report": out_dir / report_name,
    }
    write_jsonl(paths["predictions"], result.predictions)
    write_json(paths["metrics"], result.metrics)
    write_json(paths["latency"], result.latency)
    write_jsonl(paths["errors"], result.errors)
    write_report(paths["report"], result.metrics, result.latency, result.errors)
    return {name: str(path) for name, path in paths.items()}


def aggregate_latency(predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    stages: dict[str, dict[str, float | int] | None] = {}
    for stage in LATENCY_STAGES:
        values = [
            float(row["latency_ms"][stage])
            for row in predictions
            if isinstance(row.get("latency_ms"), dict) and row["latency_ms"].get(stage) is not None
        ]
        stages[stage] = _distribution(values) if values else None
    return {"unit": "milliseconds", "stages": stages}


def aggregate_agent_metrics(predictions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Derive agent metrics with explicit, stable denominators."""
    total = len(predictions)
    attempted = sum(int(row.get("tool_call_count") or 0) for row in predictions)
    successful_calls = sum(int(row.get("successful_tool_calls") or 0) for row in predictions)
    abstained = sum(row.get("agent_status") == "abstained" for row in predictions)
    failures = sum(row.get("agent_status") == "failed" or row.get("failed_stage") == "agent_execution" for row in predictions)
    step_limits = sum(row.get("agent_reason_code") == "step_limit_reached" for row in predictions)
    empty = sum(row.get("agent_reason_code") == "empty_context" for row in predictions)
    invoked = sum(bool(row.get("retrieval_invoked")) for row in predictions)
    return {
        "denominators": {"cases": total, "attempted_tool_calls": attempted},
        "tool_call_success_rate": successful_calls / attempted if attempted else None,
        "retrieval_invocation_rate": invoked / total if total else None,
        "average_tool_calls_per_case": attempted / total if total else None,
        "planner_abstention_rate": abstained / total if total else None,
        "step_limit_failure_rate": step_limits / total if total else None,
        "empty_context_rate": empty / total if total else None,
        "agent_failure_rate": failures / total if total else None,
    }


def score_case(
    qa: dict[str, Any],
    index: int,
    predicted: str,
    reference_answer: str,
    chunks: Sequence[Any],
) -> dict[str, Any]:
    answer_type = str(qa.get("answer_type") or "").lower()
    category = str(qa.get("category") or "").lower()
    ground_truth = qa.get("ground_truth") or {}
    ground_truth_chunks = {str(value) for value in ground_truth.get("chunk_ids") or [] if value}
    retrieved = {str(getattr(chunk, "chunk_id", "")) for chunk in chunks}
    unanswerable = answer_type == "unanswerable" or category == "unanswerable"
    unanswerable_ok = is_unanswerable_text(predicted) if unanswerable else not is_unanswerable_text(predicted)
    context_recall = (
        len(ground_truth_chunks & retrieved) / len(ground_truth_chunks)
        if ground_truth_chunks
        else (1.0 if unanswerable else 0.0)
    )
    return {
        "qa_id": qa_id(qa, index),
        "question": qa.get("question"),
        "category": qa.get("category"),
        "difficulty": qa.get("difficulty"),
        "answer_type": qa.get("answer_type"),
        "reference_answer": reference_answer,
        "predicted_answer": predicted,
        "ground_truth": ground_truth,
        "exact_match": exact_match(
            _answer_for_exact_match(predicted, answer_type),
            _answer_for_exact_match(reference_answer, answer_type),
        ),
        "token_f1": token_f1(predicted, reference_answer),
        "rouge_l": rouge_l(predicted, reference_answer),
        "unanswerable_accuracy": 1.0 if unanswerable_ok else 0.0,
        "context_recall@k": context_recall,
    }


def format_context(chunks: Sequence[Any]) -> str:
    return format_context_for_prompt(chunks)


def write_report(
    path: Path,
    metrics: dict[str, Any],
    latency: dict[str, Any],
    errors: Sequence[dict[str, Any]],
) -> None:
    counts = metrics["counts"]
    config = metrics.get("config") or {}
    lines = [
        "# End-to-End RAG Evaluation Report",
        "",
        f"- QA path: `{metrics.get('qa_path') or 'in-memory fixture'}`",
        f"- Total input: {counts['total_input']}",
        f"- Successful/evaluated: {counts['successful']}",
        f"- Failed: {counts['failed']}",
        f"- Skipped: {counts['skipped']}",
        "- Quality metric denominator: successful cases only",
        "- Latency denominator: cases with a recorded value for each stage",
        f"- Generator: `{config.get('generator_model') or config.get('generation', {}).get('model') or 'custom'}`",
        f"- Retrieval top-k: {config.get('retrieval_top_k') or config.get('retrieval', {}).get('top_k') or 'n/a'}",
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    overall = metrics["overall"]
    lines.extend(f"| {key} | {overall.get(key, 0.0):.4f} |" for key in metrics["metric_keys"])
    for title, key in (
        ("By Category", "by_category"),
        ("By Answer Type", "by_answer_type"),
        ("By Difficulty", "by_difficulty"),
    ):
        lines.extend(["", f"## {title}", ""])
        lines.extend(_group_table(metrics[key], metrics["metric_keys"]))

    lines.extend(
        [
            "",
            "## Stage Latency",
            "",
            "| Stage | Count | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | P95 (ms) |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for stage in LATENCY_STAGES:
        values = latency["stages"].get(stage)
        if values is None:
            lines.append(f"| {stage} | 0 | — | — | — | — | — |")
        else:
            lines.append(
                f"| {stage} | {values['count']} | {values['mean']:.3f} | {values['median']:.3f} | "
                f"{values['min']:.3f} | {values['max']:.3f} | {values['p95']:.3f} |"
            )

    failure_counts = Counter(str(error.get("stage") or "unknown") for error in errors)
    lines.extend(["", "## Failures", "", f"- Failed cases: {len(errors)}", "- Artifact: `errors.jsonl`"])
    if failure_counts:
        lines.extend(["", "| Stage | Count |", "| --- | ---: |"])
        lines.extend(f"| {stage} | {count} |" for stage, count in failure_counts.most_common())
    else:
        lines.append("- No case failures recorded.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _retrieve_with_latency(
    retriever: Any,
    question: str,
    *,
    filter_profile: str,
    top_k: int,
) -> tuple[Any, dict[str, float | None]]:
    if hasattr(retriever, "retrieve_with_latency"):
        result, breakdown = retriever.retrieve_with_latency(
            question,
            top_k=max(top_k * 3, top_k),
            top_n=top_k,
            filter_profile=filter_profile,
        )
        return result, _latency_breakdown_to_ms(breakdown, retriever=retriever)

    started = time.perf_counter()
    result = retriever.retrieve(question, filter_profile=filter_profile, top_n=top_k)
    latency = _empty_latency()
    latency["dense_retrieval"] = _elapsed_ms(started)
    return result, latency


def _latency_breakdown_to_ms(breakdown: Any, *, retriever: Any) -> dict[str, float | None]:
    raw = vars(breakdown) if hasattr(breakdown, "__dict__") else breakdown.to_dict()
    latency = _empty_latency()
    mappings = {
        "dense_latency_s": "dense_retrieval",
        "sparse_latency_s": "sparse_retrieval",
        "graph_latency_s": "graph_traversal",
        "graph_traversal_latency_s": "graph_traversal",
        "fusion_latency_s": "fusion",
        "cross_encoder_latency_s": "reranker",
        "rerank_latency_s": "reranker",
    }
    for source, target in mappings.items():
        if target == "reranker" and hasattr(retriever, "use_cross_encoder") and not retriever.use_cross_encoder:
            continue
        if source in raw and raw[source] is not None:
            latency[target] = float(raw[source]) * 1000.0
    return latency


def _chunk_to_dict(chunk: Any, rank: int) -> dict[str, Any]:
    rerank_score = getattr(chunk, "rerank_score", None)
    vector_score = getattr(chunk, "vector_score", None)
    return {
        "rank": rank,
        "chunk_id": getattr(chunk, "chunk_id", None),
        "document_id": getattr(chunk, "id_str", None),
        "provision_id": getattr(chunk, "parent_unit_id", None),
        "title": getattr(chunk, "title", None),
        "section": getattr(chunk, "section", None),
        "article_number": getattr(chunk, "article_number", None),
        "page": getattr(chunk, "page", None),
        "unit_type": getattr(chunk, "unit_type", None),
        "path": getattr(chunk, "path", None),
        "source_path": getattr(chunk, "source_path", None) or getattr(chunk, "path", None),
        "url": getattr(chunk, "url", None),
        "text": getattr(chunk, "chunk_text", None),
        "score": rerank_score if rerank_score is not None else vector_score,
        "vector_score": vector_score,
        "rerank_score": rerank_score,
        "citation_anchor": getattr(chunk, "citation_anchor", None),
        "citation_label": getattr(chunk, "citation_label", None),
        "citation": getattr(chunk, "citation_anchor", None) or getattr(chunk, "citation_label", None),
    }


def _answer_for_exact_match(answer: str, answer_type: str) -> str:
    if answer_type == "boolean":
        for line in answer.splitlines():
            if line.strip():
                return line.strip()
    return answer


def _empty_latency() -> dict[str, float | None]:
    return {stage: None for stage in LATENCY_STAGES}


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 6)


def _distribution(values: Sequence[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "count": len(ordered),
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "min": ordered[0],
        "max": ordered[-1],
        "p95": ordered[p95_index],
    }


def _error_record(
    *,
    case_identifier: str,
    stage: str,
    exc: Exception,
    sensitive_values: Sequence[str],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message = _sanitize_text(str(exc), sensitive_values)
    shortened_traceback = _sanitize_text(traceback.format_exc(limit=5), sensitive_values)
    record = {
        "case_id": case_identifier,
        "stage": stage,
        "exception_type": type(exc).__name__,
        "message": message,
        "traceback": shortened_traceback,
        "retryable": isinstance(exc, (TimeoutError, ConnectionError)),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if details:
        record["details"] = {
            key: _sanitize_text(value, sensitive_values) if isinstance(value, str) else value
            for key, value in details.items()
        }
    return record


def _failed_prediction(
    *,
    case_identifier: str,
    qa: dict[str, Any] | None,
    failed_stage: str,
    error_record: dict[str, Any],
    latency: dict[str, float | None],
) -> dict[str, Any]:
    qa = qa or {}
    return {
        "qa_id": case_identifier,
        "question": qa.get("question"),
        "category": qa.get("category"),
        "difficulty": qa.get("difficulty"),
        "answer_type": qa.get("answer_type"),
        "status": "failed",
        "failed_stage": failed_stage,
        "error": {
            "type": error_record["exception_type"],
            "message": error_record["message"],
        },
        "latency_ms": latency,
    }


def _sanitize_text(text: str, sensitive_values: Sequence[str]) -> str:
    sanitized = text
    for value in sensitive_values:
        if value:
            sanitized = sanitized.replace(value, "***")
    sanitized = _SECRET_PATTERNS[0].sub(r"\1\2***", sanitized)
    sanitized = _SECRET_PATTERNS[1].sub("Bearer ***", sanitized)
    return sanitized


def sanitize_error_text(text: object, sensitive_values: Sequence[str] = ()) -> str:
    """Public bounded redaction helper for non-runner service/UI diagnostics."""

    return _sanitize_text(str(text), sensitive_values)[:1000]


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _group_table(groups: dict[str, Any], metric_keys: Sequence[str]) -> list[str]:
    header = ["Group", "Count", *metric_keys]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---", "---:"] + ["---:"] * len(metric_keys)) + " |",
    ]
    for group, values in groups.items():
        cells = [group, str(values.get("count", 0)), *[f"{values.get(key, 0.0):.4f}" for key in metric_keys]]
        lines.append("| " + " | ".join(cells) + " |")
    return lines
