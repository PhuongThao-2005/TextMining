#!/usr/bin/env python3
"""Derive the candidate-controlled reranker ablation metrics.

The six refreshed runs share the same 500 QA ids and the same cached dense and
BM25 top-30 lists.  This module reconstructs the RRF top-30 candidate pool,
validates it against the recorded RRF-only output, computes deterministic
retrieval and answerability metrics, and writes paired bootstrap summaries.

The source artifacts do not contain legal-judge labels, claim decompositions,
or explicit citation-to-chunk mappings.  Those metrics are therefore reported
as unavailable and a blinded annotation template is emitted for follow-up
evaluation.

Run from the repository root or from this directory:

    python3 ablation_work/reranker_choices/analyze_reranker_metrics.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import pickle
import random
import re
import statistics
import unicodedata
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parent
RUN_ROOT = ROOT / "evaluation_runs" / "ablation3_reranker_v2"
CACHE_ROOT = ROOT / "retrieval_cache"

CONFIGS = OrderedDict(
    [
        ("None", "Rerank-None-Hybrid"),
        ("RRF-only", "Rerank-RRF-Hybrid"),
        ("mMiniLM", "Rerank-CrossEncoder-Hybrid"),
        ("Qwen3", "Rerank-Qwen3Reranker-Hybrid"),
        ("BGE", "Rerank-BGEReranker-Hybrid"),
        ("Jina", "Rerank-JinaReranker-Hybrid"),
    ]
)
RERANKERS = ("mMiniLM", "Qwen3", "BGE", "Jina")
PRIMARY_BASELINE = "RRF-only"
RETRIEVAL_METRICS = ("hit@1", "recall@10", "mrr@10", "ndcg@10")
PAIRED_METRICS = ("recall@10", "mrr@10", "ndcg@10", "token_f1", "rouge_l")
SLICE_METRICS = ("recall@10", "mrr@10", "ndcg@10")
LOWER_IS_BETTER = {"false_refusal_rate"}

SLICE_SPECS = (
    ("category", "citation"),
    ("category", "legal_validity"),
    ("category", "single_hop"),
    ("category", "multi_hop"),
    ("answer_type", "extractive"),
    ("answer_type", "abstractive"),
    ("answer_type", "boolean"),
)

# The benchmark's generated refusal answers use Vietnamese phrases.  Matching
# is accent-insensitive and includes the phrase used in the refreshed runs.
ABSTENTION_MARKERS = (
    "khong co du thong tin",
    "khong du thong tin",
    "khong du can cu",
    "khong duoc neu",
    "khong tim thay",
    "khong co thong tin",
    "khong the xac dinh",
    "khong co trong ngu canh",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected an object at {path}:{line_number}")
        rows.append(value)
    return rows


def load_rows(config_dir: str) -> dict[str, dict[str, Any]]:
    path = RUN_ROOT / config_dir / "retrieval_cases.jsonl"
    rows = read_jsonl(path)
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        qa_id = str(row.get("qa_id", ""))
        if not qa_id:
            raise ValueError(f"Missing qa_id in {path}")
        if qa_id in by_id:
            raise ValueError(f"Duplicate qa_id {qa_id!r} in {path}")
        by_id[qa_id] = row
    return by_id


def load_manifest(config_dir: str) -> dict[str, Any]:
    return json.loads((RUN_ROOT / config_dir / "manifest.json").read_text(encoding="utf-8"))


def validate_manifests() -> dict[str, Any]:
    """Validate the controlled settings recorded for every evaluation run."""

    manifests = {
        name: load_manifest(config_dir) for name, config_dir in CONFIGS.items()
    }
    common_fields = (
        "eval_count",
        "embedding_model",
        "generator_model",
        "top_k",
        "top_n",
        "rrf_k",
        "ce_candidate_mult",
        "device",
    )
    expected = {
        "eval_count": 500,
        "top_k": 30,
        "top_n": 10,
        "rrf_k": 60,
    }
    for name, manifest in manifests.items():
        config_dir = CONFIGS[name]
        if manifest.get("config") != config_dir:
            raise ValueError(
                f"Manifest config mismatch for {name}: {manifest.get('config')!r}"
            )
        for field, expected_value in expected.items():
            if manifest.get(field) != expected_value:
                raise ValueError(
                    f"Unexpected {field} for {name}: {manifest.get(field)!r}; "
                    f"expected {expected_value!r}"
                )
    common_values: dict[str, Any] = {}
    for field in common_fields:
        values = {name: manifests[name].get(field) for name in CONFIGS}
        unique = set(values.values())
        if len(unique) != 1:
            raise ValueError(f"Controlled manifest field {field!r} differs: {values}")
        common_values[field] = next(iter(unique))
    return {
        "consistent": True,
        "common_parameters": common_values,
        "reranker_models": {
            name: manifests[name].get("reranker_model") for name in CONFIGS
        },
    }


def load_cache_hits(filename: str) -> list[list[Any]]:
    path = CACHE_ROOT / filename
    with path.open("rb") as handle:
        payload = pickle.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("hits"), list):
        raise ValueError(f"Unexpected cache format: {path}")
    return payload["hits"]


def hit_id(hit: Any) -> str:
    if isinstance(hit, (list, tuple)) and hit:
        return str(hit[0])
    if isinstance(hit, dict):
        value = hit.get("chunk_id") or hit.get("id") or hit.get("point_id")
        if value is not None:
            return str(value)
    raise ValueError(f"Cannot extract chunk id from cache hit: {hit!r}")


def rrf_top_30(
    dense_hits: Sequence[Any],
    bm25_hits: Sequence[Any],
    *,
    rrf_k: int = 60,
    limit: int = 30,
) -> list[str]:
    """Reconstruct the shared RRF candidate list with stable tie-breaking."""

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    order = 0
    for ranked_hits in (dense_hits, bm25_hits):
        for rank, hit in enumerate(ranked_hits, 1):
            chunk_id = hit_id(hit)
            if chunk_id not in first_seen:
                first_seen[chunk_id] = order
                order += 1
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return [
        chunk_id
        for chunk_id, _score in sorted(
            scores.items(), key=lambda item: (-item[1], first_seen[item[0]])
        )[:limit]
    ]


def normalize_for_matching(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_abstention(value: Any) -> bool:
    normalized = normalize_for_matching(value)
    return any(marker in normalized for marker in ABSTENTION_MARKERS)


def is_answerable(row: dict[str, Any]) -> bool:
    return not bool(row.get("is_unanswerable"))


def gold_ids(row: dict[str, Any]) -> set[str]:
    return {str(value) for value in (row.get("ground_truth_chunk_ids") or [])}


def retrieved_ids(row: dict[str, Any]) -> list[str]:
    return [str(value) for value in (row.get("retrieved_chunk_ids") or [])]


def recall_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    return len(set(retrieved[:k]) & gold) / len(gold) if gold else 0.0


def hit_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    return 1.0 if gold and set(retrieved[:k]) & gold else 0.0


def mrr_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    for rank, chunk_id in enumerate(retrieved[:k], 1):
        if chunk_id in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, chunk_id in enumerate(retrieved[:k], 1)
        if chunk_id in gold
    )
    ideal_hits = min(len(gold), k)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def mean(values: Iterable[float | None]) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    return statistics.fmean(filtered) if filtered else None


def percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def win_tie_loss(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    lower_is_better: bool = False,
) -> dict[str, int]:
    if len(candidate) != len(baseline):
        raise ValueError("Paired vectors have different lengths")
    wins = ties = losses = 0
    for treatment, control in zip(candidate, baseline):
        if treatment == control:
            ties += 1
        elif (treatment < control) if lower_is_better else (treatment > control):
            wins += 1
        else:
            losses += 1
    return {"wins": wins, "ties": ties, "losses": losses}


def bootstrap_delta_ci(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    replicates: int,
    seed: int,
) -> tuple[float, list[float]]:
    """Return the observed delta and a percentile paired-bootstrap interval."""

    if len(candidate) != len(baseline) or not candidate:
        raise ValueError("Bootstrap vectors must be paired and non-empty")
    deltas = [float(treatment) - float(control) for treatment, control in zip(candidate, baseline)]
    observed = statistics.fmean(deltas)
    rng = random.Random(seed)
    n = len(deltas)
    bootstrap_means: list[float] = []
    for _ in range(replicates):
        sample = rng.choices(deltas, k=n)
        bootstrap_means.append(statistics.fmean(sample))
    return observed, [float(percentile(bootstrap_means, 0.025)), float(percentile(bootstrap_means, 0.975))]


def paired_summary(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    replicates: int,
    seed: int,
    lower_is_better: bool = False,
) -> dict[str, Any]:
    delta, ci95 = bootstrap_delta_ci(
        candidate, baseline, replicates=replicates, seed=seed
    )
    return {
        "baseline_mean": statistics.fmean(baseline),
        "candidate_mean": statistics.fmean(candidate),
        "delta": delta,
        "ci95": ci95,
        "win_tie_loss": win_tie_loss(
            candidate, baseline, lower_is_better=lower_is_better
        ),
    }


def build_candidate_pools(
    rows_by_config: dict[str, dict[str, dict[str, Any]]],
    *,
    rrf_k: int,
    limit: int,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    """Build C30 and validate cache alignment against the recorded RRF output."""

    dense = load_cache_hits("dense_all_hits.pkl")
    bm25 = load_cache_hits("bm25_all_hits.pkl")
    rrf_rows = rows_by_config[PRIMARY_BASELINE]
    ordered_ids = list(rrf_rows)
    if len(dense) != len(bm25) or len(dense) != len(ordered_ids):
        raise ValueError(
            "Dense/BM25 cache length and RRF evaluation row count do not match: "
            f"dense={len(dense)}, bm25={len(bm25)}, rows={len(ordered_ids)}"
        )

    pools: dict[str, list[str]] = {}
    exact_matches = 0
    mismatches: list[dict[str, Any]] = []
    for index, qa_id in enumerate(ordered_ids):
        pool = rrf_top_30(dense[index], bm25[index], rrf_k=rrf_k, limit=limit)
        pools[qa_id] = pool
        recorded = retrieved_ids(rrf_rows[qa_id])
        if pool[: len(recorded)] == recorded:
            exact_matches += 1
        elif len(mismatches) < 5:
            mismatches.append(
                {"qa_id": qa_id, "reconstructed_top10": pool[:10], "recorded_top10": recorded}
            )

    validation = {
        "dense_cache_queries": len(dense),
        "bm25_cache_queries": len(bm25),
        "dense_cache_length_range": [min(map(len, dense)), max(map(len, dense))],
        "bm25_cache_length_range": [min(map(len, bm25)), max(map(len, bm25))],
        "candidate_pool_size": limit,
        "rrf_k": rrf_k,
        "rrf_recorded_top10_exact_matches": exact_matches,
        "rrf_recorded_top10_total": len(ordered_ids),
        "rrf_recorded_top10_alignment": not mismatches and exact_matches == len(ordered_ids),
        "alignment_examples": mismatches,
    }
    if not validation["rrf_recorded_top10_alignment"]:
        raise ValueError(f"Reconstructed RRF pool does not match recorded output: {validation}")
    return pools, validation


def candidate_controlled_metrics(
    rows: dict[str, dict[str, Any]],
    pools: dict[str, list[str]],
) -> dict[str, Any]:
    answerable = [row for row in rows.values() if is_answerable(row)]
    candidate_recall: list[float] = []
    candidate_hit: list[float] = []
    retention: list[float] = []
    preservation: list[float] = []
    out_of_pool = 0
    for row in answerable:
        qa_id = str(row["qa_id"])
        gold = gold_ids(row)
        pool = pools[qa_id]
        final = retrieved_ids(row)
        available = gold & set(pool)
        retained = available & set(final)
        candidate_recall.append(len(available) / len(gold))
        candidate_hit.append(1.0 if available else 0.0)
        if available:
            retention.append(len(retained) / len(available))
            preservation.append(1.0 if retained else 0.0)
        if not set(final).issubset(set(pool)):
            out_of_pool += 1

    return {
        "answerable_count": len(answerable),
        "candidate_recall_at_30": statistics.fmean(candidate_recall),
        "candidate_hit_at_30": statistics.fmean(candidate_hit),
        "gold_retention_at_10": statistics.fmean(retention) if retention else None,
        "candidate_hit_preservation_at_10": statistics.fmean(preservation) if preservation else None,
        "candidate_hit_queries": len(retention),
        "final_context_out_of_pool_queries": out_of_pool,
    }


def headline_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in rows.values() if is_answerable(row)]
    if not answerable:
        raise ValueError("No answerable rows found")
    retrieval = {
        "hit@1": mean(hit_at_k(retrieved_ids(row), gold_ids(row), 1) for row in answerable),
        "hit@10": mean(hit_at_k(retrieved_ids(row), gold_ids(row), 10) for row in answerable),
        "recall@10": mean(recall_at_k(retrieved_ids(row), gold_ids(row), 10) for row in answerable),
        "mrr@10": mean(mrr_at_k(retrieved_ids(row), gold_ids(row), 10) for row in answerable),
        "ndcg@10": mean(ndcg_at_k(retrieved_ids(row), gold_ids(row), 10) for row in answerable),
    }
    answer = {
        metric: mean(row.get(metric) for row in answerable)
        for metric in ("exact_match", "token_f1", "rouge_l")
    }
    return {"count": len(answerable), "retrieval": retrieval, "answer_overlap": answer}


def build_case_metrics(
    rows_by_config: dict[str, dict[str, dict[str, Any]]],
    answerable_ids: Sequence[str],
) -> dict[str, dict[str, dict[str, float]]]:
    values: dict[str, dict[str, dict[str, float]]] = {}
    for name, rows in rows_by_config.items():
        config_values: dict[str, dict[str, float]] = {}
        for qa_id in answerable_ids:
            row = rows[qa_id]
            retrieved = retrieved_ids(row)
            gold = gold_ids(row)
            config_values[qa_id] = {
                "hit@1": hit_at_k(retrieved, gold, 1),
                "recall@10": recall_at_k(retrieved, gold, 10),
                "mrr@10": mrr_at_k(retrieved, gold, 10),
                "ndcg@10": ndcg_at_k(retrieved, gold, 10),
                "token_f1": float(row["token_f1"]),
                "rouge_l": float(row["rouge_l"]),
                "exact_match": float(row["exact_match"]),
                "false_refusal_rate": 1.0 if is_abstention(row.get("predicted_answer")) else 0.0,
            }
        values[name] = config_values
    return values


def answerability_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in rows.values() if is_answerable(row)]
    unanswerable = [row for row in rows.values() if not is_answerable(row)]
    true_abstain = sum(is_abstention(row.get("predicted_answer")) for row in unanswerable)
    true_answer = sum(not is_abstention(row.get("predicted_answer")) for row in answerable)
    false_answer = sum(not is_abstention(row.get("predicted_answer")) for row in unanswerable)
    false_refusal = sum(is_abstention(row.get("predicted_answer")) for row in answerable)
    predicted_abstain = true_abstain + false_refusal
    precision = true_abstain / predicted_abstain if predicted_abstain else 0.0
    recall = true_abstain / len(unanswerable) if unanswerable else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    recorded = mean(row.get("unanswerable_accuracy") for row in rows.values())
    return {
        "total_count": len(rows),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "true_abstain": true_abstain,
        "true_answer": true_answer,
        "false_refusal": false_refusal,
        "false_answer": false_answer,
        "answerability_accuracy": (true_abstain + true_answer) / len(rows) if rows else 0.0,
        "recorded_unanswerable_accuracy_mean": recorded,
        "abstain_precision": precision,
        "abstain_recall": recall,
        "abstain_f1": f1,
        "answerable_acceptance": true_answer / len(answerable) if answerable else 0.0,
        "false_refusal_rate": false_refusal / len(answerable) if answerable else 0.0,
        "false_answer_rate": false_answer / len(unanswerable) if unanswerable else 0.0,
        "classifier": {
            "type": "deterministic accent-insensitive refusal-marker classifier",
            "markers": list(ABSTENTION_MARKERS),
        },
    }


def latency_metrics(config_dir: str, evaluated_count: int) -> dict[str, Any]:
    path = RUN_ROOT / config_dir / "latency.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    average = payload.get("avg", {})
    median = payload.get("median", {})
    total_run_time = payload.get("total_run_time_s")
    sparse_mean = average.get("sparse_latency_s")
    p95 = payload.get("p95", {})
    return {
        "total_run_time_s": total_run_time,
        "observed_run_throughput_qps": (
            evaluated_count / float(total_run_time) if total_run_time else None
        ),
        "reranker_mean_s": average.get("cross_encoder_latency_s"),
        "reranker_p50_s": median.get("cross_encoder_latency_s"),
        "reranker_p95_s": p95.get("cross_encoder_latency_s"),
        "total_mean_s": average.get("total_latency_s"),
        "total_p50_s": median.get("total_latency_s"),
        "total_p95_s": p95.get("total_latency_s"),
        "dense_mean_s": average.get("dense_latency_s"),
        "sparse_mean_s": sparse_mean,
        "fusion_mean_s": average.get("fusion_latency_s"),
        "generation_mean_s": average.get("generation_latency_s"),
        "full_online_bm25_latency_recorded": bool(sparse_mean and sparse_mean > 0),
        "raw_latency_path": str(path),
    }


def paired_vectors(
    case_values: dict[str, dict[str, dict[str, float]]],
    candidate: str,
    baseline: str,
    qa_ids: Sequence[str],
    metric: str,
) -> tuple[list[float], list[float]]:
    treatment = [case_values[candidate][qa_id][metric] for qa_id in qa_ids]
    control = [case_values[baseline][qa_id][metric] for qa_id in qa_ids]
    return treatment, control


def paired_effects(
    case_values: dict[str, dict[str, dict[str, float]]],
    *,
    answerable_ids: Sequence[str],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    baseline = PRIMARY_BASELINE
    for candidate_index, candidate in enumerate(RERANKERS):
        metrics: dict[str, Any] = {}
        for metric_index, metric in enumerate((*PAIRED_METRICS, "false_refusal_rate")):
            treatment, control = paired_vectors(
                case_values, candidate, baseline, answerable_ids, metric
            )
            metrics[metric] = paired_summary(
                treatment,
                control,
                replicates=replicates,
                seed=seed + (candidate_index + 1) * 100 + metric_index,
                lower_is_better=metric in LOWER_IS_BETTER,
            )
        result[candidate] = metrics
    return result


def slice_effects(
    case_values: dict[str, dict[str, dict[str, float]]],
    rows: dict[str, dict[str, dict[str, Any]]],
    *,
    answerable_ids: Sequence[str],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    rrf_rows = rows[PRIMARY_BASELINE]
    for dimension, value in SLICE_SPECS:
        slice_ids = [
            qa_id
            for qa_id in answerable_ids
            if str(rrf_rows[qa_id].get(dimension)) == value
        ]
        dimension_result = result.setdefault(dimension, {})
        group = {
            "count": len(slice_ids),
            "exploratory": len(slice_ids) < 30,
            "vs_rrf": {},
        }
        for candidate_index, candidate in enumerate(RERANKERS):
            candidate_result: dict[str, Any] = {}
            for metric_index, metric in enumerate(SLICE_METRICS):
                treatment, control = paired_vectors(
                    case_values, candidate, PRIMARY_BASELINE, slice_ids, metric
                )
                if slice_ids:
                    candidate_result[metric] = paired_summary(
                        treatment,
                        control,
                        replicates=replicates,
                        seed=seed + candidate_index * 1000 + metric_index + len(slice_ids),
                    )
                else:
                    candidate_result[metric] = None
            group["vs_rrf"][candidate] = candidate_result
        dimension_result[value] = group
    return result


def annotation_records(
    rows_by_config: dict[str, dict[str, dict[str, Any]]],
    answerable_ids: Sequence[str],
    *,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    system_ids = {
        name: f"system_{index:02d}"
        for index, name in enumerate(CONFIGS, 1)
    }
    records: list[dict[str, Any]] = []
    for name, rows in rows_by_config.items():
        system_id = system_ids[name]
        for qa_id in answerable_ids:
            row = rows[qa_id]
            predicted = str(row.get("predicted_answer") or "")
            records.append(
                {
                    "annotation_id": hashlib.sha1(
                        f"{system_id}:{qa_id}".encode("utf-8")
                    ).hexdigest()[:16],
                    "system_id": system_id,
                    "qa_id": qa_id,
                    "question": row.get("question"),
                    "reference_answer": row.get("reference_answer"),
                    "predicted_answer": predicted,
                    "retrieved_chunk_ids": retrieved_ids(row),
                    "citation_count": int(row.get("citation_count") or 0),
                    "citation_markers": sorted(
                        {int(value) for value in re.findall(r"\[(\d+)\]", predicted)}
                    ),
                    "citation_to_chunk_mapping": None,
                    "labels": {
                        "legal_correctness_0_2": None,
                        "completeness_0_2": None,
                        "claim_faithfulness_fraction": None,
                        "citation_precision_fraction": None,
                        "citation_recall_fraction": None,
                    },
                }
            )
    random.Random(seed).shuffle(records)
    key = {system_id: name for name, system_id in system_ids.items()}
    return records, key


def f4(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def f3(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def pct(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def delta_ci(summary: dict[str, Any] | None) -> str:
    if not summary:
        return "N/A"
    delta = summary["delta"]
    lo, hi = summary["ci95"]
    return f"{delta:+.4f} [{lo:+.4f}, {hi:+.4f}]"


def wtl(summary: dict[str, Any] | None) -> str:
    if not summary:
        return "N/A"
    counts = summary["win_tie_loss"]
    return f"{counts['wins']} / {counts['ties']} / {counts['losses']}"


def write_annotation_files(
    rows_by_config: dict[str, dict[str, dict[str, Any]]],
    answerable_ids: Sequence[str],
    *,
    seed: int,
) -> tuple[Path, Path, int]:
    records, key = annotation_records(rows_by_config, answerable_ids, seed=seed)
    template_path = RUN_ROOT / "answer_annotation_template.jsonl"
    key_path = RUN_ROOT / "answer_annotation_key.json"
    template_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    key_path.write_text(
        json.dumps(key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return template_path, key_path, len(records)


def write_svg_forest(data: dict[str, Any], path: Path) -> None:
    entries: list[tuple[str, str, float | None, list[float] | None]] = []
    for metric in ("ndcg@10", "recall@10", "mrr@10"):
        for candidate in RERANKERS:
            summary = data["paired_vs_rrf"][candidate][metric]
            entries.append((metric, candidate, summary["delta"], summary["ci95"]))
    values = [value for _metric, _name, value, _ci in entries if value is not None]
    bounds = [bound for _metric, _name, _value, ci in entries if ci for bound in ci]
    lo = min(bounds + values + [0.0]) - 0.02
    hi = max(bounds + values + [0.0]) + 0.02
    width, height = 1100, 760
    left, right, top, bottom = 270, 80, 70, 70
    plot_width = width - left - right
    row_height = 27
    plot_rows = 3 * len(RERANKERS)

    def x(value: float) -> float:
        return left + (value - lo) / (hi - lo) * plot_width

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,sans-serif;fill:#243447}.title{font-size:20px;font-weight:700}.axis{font-size:12px}.group{font-size:14px;font-weight:700}.row{font-size:13px}.note{font-size:12px;fill:#52606d}</style>',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{left}" y="30" class="title">Paired effects versus RRF-only</text>',
        f'<text x="{left}" y="50" class="note">Candidate minus RRF-only; 95% paired-bootstrap percentile CI</text>',
    ]
    for tick in range(5):
        value = lo + (hi - lo) * tick / 4
        x_value = x(value)
        lines.append(f'<line x1="{x_value:.2f}" y1="{top}" x2="{x_value:.2f}" y2="{height-bottom}" stroke="#e5e7eb"/>')
        lines.append(f'<text x="{x_value:.2f}" y="{height-bottom+22}" text-anchor="middle" class="axis">{value:+.2f}</text>')
    zero_x = x(0.0)
    lines.append(f'<line x1="{zero_x:.2f}" y1="{top-8}" x2="{zero_x:.2f}" y2="{height-bottom}" stroke="#b91c1c" stroke-width="2" stroke-dasharray="5,4"/>')
    colors = {"mMiniLM": "#2563eb", "Qwen3": "#9333ea", "BGE": "#059669", "Jina": "#ea580c"}
    y = top + 18
    for metric, candidate, value, ci in entries:
        if candidate == RERANKERS[0]:
            lines.append(f'<text x="20" y="{y-8}" class="group">{html.escape(metric)}</text>')
        if value is not None and ci is not None:
            lo_ci, hi_ci = ci
            lines.append(f'<text x="{left-12}" y="{y+4}" text-anchor="end" class="row">{html.escape(candidate)}</text>')
            lines.append(f'<line x1="{x(lo_ci):.2f}" y1="{y}" x2="{x(hi_ci):.2f}" y2="{y}" stroke="{colors[candidate]}" stroke-width="3"/>')
            lines.append(f'<line x1="{x(lo_ci):.2f}" y1="{y-5}" x2="{x(lo_ci):.2f}" y2="{y+5}" stroke="{colors[candidate]}"/>')
            lines.append(f'<line x1="{x(hi_ci):.2f}" y1="{y-5}" x2="{x(hi_ci):.2f}" y2="{y+5}" stroke="{colors[candidate]}"/>')
            lines.append(f'<circle cx="{x(value):.2f}" cy="{y}" r="5" fill="{colors[candidate]}"/>')
        y += row_height
        if candidate == RERANKERS[-1]:
            y += 12
    lines.extend(
        [
            f'<text x="20" y="{height-35}" class="group">Legal correctness</text>',
            f'<text x="{left}" y="{height-35}" class="note">N/A — blinded legal annotations are not present in the source artifacts</text>',
            f'<text x="{left}" y="{height-10}" class="note">Positive values favor the reranker. The CI reflects benchmark sampling, not generator reruns.</text>',
            '</svg>',
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_svg_pareto(data: dict[str, Any], path: Path) -> None:
    points: list[tuple[str, float, float]] = []
    for name in CONFIGS:
        latency = data["latency"][name]["total_p50_s"]
        ndcg = data["headline"][name]["retrieval"]["ndcg@10"]
        if latency is not None and ndcg is not None:
            points.append((name, float(latency), float(ndcg)))
    max_x = max(point[1] for point in points) * 1.15
    max_y = max(point[2] for point in points) * 1.15
    width, height = 1000, 620
    left, right, top, bottom = 100, 60, 70, 90
    plot_width = width - left - right
    plot_height = height - top - bottom

    def x(value: float) -> float:
        return left + value / max_x * plot_width

    def y(value: float) -> float:
        return top + plot_height - value / max_y * plot_height

    colors = {"None": "#64748b", "RRF-only": "#0f766e", "mMiniLM": "#2563eb", "Qwen3": "#9333ea", "BGE": "#059669", "Jina": "#ea580c"}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<style>text{font-family:Arial,sans-serif;fill:#243447}.title{font-size:20px;font-weight:700}.axis{font-size:12px}.note{font-size:12px;fill:#52606d}</style>',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{left}" y="30" class="title">nDCG@10 versus p50 total latency</text>',
        f'<text x="{left}" y="50" class="note">Current cached-retrieval run; lower-left is faster but lower quality</text>',
        f'<line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" stroke="#334155"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#334155"/>',
        f'<text x="{left+plot_width/2:.1f}" y="{height-35}" text-anchor="middle" class="axis">Total latency p50 (seconds)</text>',
        f'<text x="22" y="{top+plot_height/2:.1f}" transform="rotate(-90 22 {top+plot_height/2:.1f})" text-anchor="middle" class="axis">nDCG@10</text>',
    ]
    for tick in range(6):
        value = max_x * tick / 5
        x_value = x(value)
        lines.append(f'<line x1="{x_value:.2f}" y1="{top}" x2="{x_value:.2f}" y2="{top+plot_height}" stroke="#eef2f7"/>')
        lines.append(f'<text x="{x_value:.2f}" y="{top+plot_height+20}" text-anchor="middle" class="axis">{value:.1f}</text>')
    for tick in range(6):
        value = max_y * tick / 5
        y_value = y(value)
        lines.append(f'<line x1="{left}" y1="{y_value:.2f}" x2="{left+plot_width}" y2="{y_value:.2f}" stroke="#eef2f7"/>')
        lines.append(f'<text x="{left-10}" y="{y_value+4:.2f}" text-anchor="end" class="axis">{value:.2f}</text>')
    for name, latency, ndcg in points:
        color = colors[name]
        px, py = x(latency), y(ndcg)
        lines.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="7" fill="{color}"/>')
        lines.append(f'<text x="{px+10:.2f}" y="{py+4:.2f}" class="axis">{html.escape(name)}</text>')
    lines.extend(
        [
            f'<text x="{left}" y="{height-10}" class="note">Claim faithfulness is not plotted because no claim-level annotations are available.</text>',
            '</svg>',
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_markdown(data: dict[str, Any], path: Path) -> None:
    lines: list[str] = [
        "# Derived Metrics: Multi-Reranker Ablation",
        "",
        "This report implements the deterministic portions of `metrics_plan.md` "
        "against the refreshed `ablation3_reranker_v2` artifacts. Retrieval "
        "metrics use 400 answerable questions; answerability metrics use all "
        "500 questions. The four rerankers are compared with RRF-only, the "
        "primary shared-fusion baseline. None is retained as a separate fusion "
        "control.",
        "",
        "## 1. Validation and candidate pool",
        "",
        f"- Configurations: {len(CONFIGS)}; every run contains 500 cases, "
        f"including 400 answerable and 100 unanswerable questions.",
        f"- Controlled manifest settings agree across runs: **{data['manifest_validation']['consistent']}** "
        f"(`top_k={data['manifest_validation']['common_parameters']['top_k']}`, "
        f"`top_n={data['manifest_validation']['common_parameters']['top_n']}`, "
        f"`rrf_k={data['manifest_validation']['common_parameters']['rrf_k']}`).",
        f"- Same QA-id set across configurations: **{data['validation']['same_qa_id_set']}**.",
        f"- Reconstructed RRF C30 matches recorded RRF-only T10 exactly for "
        f"**{data['candidate_pool_validation']['rrf_recorded_top10_exact_matches']}/"
        f"{data['candidate_pool_validation']['rrf_recorded_top10_total']}** cases.",
        f"- RRF parameters: `rrf_k={data['candidate_pool_validation']['rrf_k']}`, "
        f"candidate limit `C30`.",
        f"- Recomputed headline values agree with `comparison.csv` within a maximum "
        f"absolute difference of **{data['source_consistency']['max_abs_difference']:.6f}**.",
        "",
        "The candidate pool is reconstructed from the shared dense and BM25 "
        "top-30 caches using reciprocal-rank fusion. Because the reconstruction "
        "matches the recorded RRF-only top-10 for every query, it is used as the "
        "fixed candidate pool for the retention analysis.",
        "",
        "## 2. Table 1 — Candidate-controlled retrieval",
        "",
        "Gold retention is conditional on at least one gold chunk being available "
        "in C30. Values are absolute metric values, not percentage points.",
        "",
        "| Model | Candidate Recall@30 | Candidate Hit@30 | Gold retention@10 | Candidate-hit preservation@10 | nDCG@10 | Recall@10 | MRR@10 | Hit@1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in CONFIGS:
        row = data["candidate_controlled"][name]
        head = data["headline"][name]["retrieval"]
        lines.append(
            f"| {name} | {f4(row['candidate_recall_at_30'])} | "
            f"{f4(row['candidate_hit_at_30'])} | {f4(row['gold_retention_at_10'])} | "
            f"{f4(row['candidate_hit_preservation_at_10'])} | "
            f"{f4(head['ndcg@10'])} | {f4(head['recall@10'])} | "
            f"{f4(head['mrr@10'])} | {f4(head['hit@1'])} |"
        )
    lines.extend(
        [
            "",
            "## 3. Table 2 — Paired effects versus RRF-only",
            "",
            f"Deltas are reranker minus RRF-only. Overall intervals use "
            f"{data['metadata']['bootstrap_replicates']:,} paired-bootstrap "
            "replicates over answerable questions with the recorded seed. "
            "Win/tie/loss is treatment better / equal / baseline better.",
            "",
            "| Reranker | Δ nDCG@10 (95% CI) | Δ Recall@10 (95% CI) | Δ MRR@10 (95% CI) | nDCG W/T/L | Recall W/T/L | MRR W/T/L |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in RERANKERS:
        effects = data["paired_vs_rrf"][name]
        lines.append(
            f"| {name} | {delta_ci(effects['ndcg@10'])} | "
            f"{delta_ci(effects['recall@10'])} | {delta_ci(effects['mrr@10'])} | "
            f"{wtl(effects['ndcg@10'])} | {wtl(effects['recall@10'])} | "
            f"{wtl(effects['mrr@10'])} |"
        )
    lines.extend(
        [
            "",
            "### Paired safety effect versus RRF-only",
            "",
            "False-refusal deltas are reranker minus RRF-only; negative values are "
            "safer because they indicate fewer unnecessary refusals. The false-"
            "answer rate is reported in Table 3 but is not bootstrapped here because "
            "the current primary paired analysis is defined over answerable cases.",
            "",
            "| Reranker | Δ false-refusal rate (95% CI) | Win / tie / loss (lower is better) |",
            "| --- | ---: | ---: |",
        ]
    )
    for name in RERANKERS:
        effects = data["paired_vs_rrf"][name]["false_refusal_rate"]
        lines.append(
            f"| {name} | {delta_ci(effects)} | {wtl(effects)} |"
        )
    lines.extend(
        [
            "",
            "### Paired lexical diagnostics",
            "",
            "Token F1 and ROUGE-L are included as reproducible overlap diagnostics, "
            "not as substitutes for legal correctness or faithfulness.",
            "",
            "| Reranker | Δ Token F1 (95% CI) | Δ ROUGE-L (95% CI) | Token F1 W/T/L | ROUGE-L W/T/L |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in RERANKERS:
        effects = data["paired_vs_rrf"][name]
        lines.append(
            f"| {name} | {delta_ci(effects['token_f1'])} | "
            f"{delta_ci(effects['rouge_l'])} | {wtl(effects['token_f1'])} | "
            f"{wtl(effects['rouge_l'])} |"
        )
    lines.extend(
        [
            "",
            "## 4. Table 3 — Answer quality and safety",
            "",
            "The refreshed artifacts contain lexical overlap diagnostics and a "
            "deterministic answerability signal, but no legal-judge labels, "
            "claim decomposition, or explicit citation-to-chunk mapping. The "
            "judge-dependent columns are therefore intentionally marked N/A.",
            "",
            "| Model | Legal correctness | Completeness | Claim faithfulness | Citation precision | Citation recall | False-refusal rate | False-answer rate | Token F1 | ROUGE-L |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in CONFIGS:
        safety = data["answerability"][name]
        overlap = data["headline"][name]["answer_overlap"]
        lines.append(
            f"| {name} | N/A | N/A | N/A | N/A | N/A | "
            f"{pct(safety['false_refusal_rate'])} | {pct(safety['false_answer_rate'])} | "
            f"{f4(overlap['token_f1'])} | {f4(overlap['rouge_l'])} |"
        )
    lines.extend(
        [
            "",
            "## 5. Table 4 — Deployment trade-off",
            "",
            "The source latency files provide means and medians but no p95 values. "
            "They also report zero sparse latency because BM25 candidates were "
            "cached, so these are not full-online BM25 timings. Peak GPU memory "
            "and per-query throughput are not recorded; observed run throughput "
            "is shown only as a reproducibility diagnostic.",
            "",
            "| Model | Reranker p50 / p95 | Total p50 / p95 | Observed run throughput | Peak GPU memory |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in CONFIGS:
        timing = data["latency"][name]
        throughput = timing["observed_run_throughput_qps"]
        lines.append(
            f"| {name} | {f3(timing['reranker_p50_s'])} s / N/A | "
            f"{f3(timing['total_p50_s'])} s / N/A | "
            f"{f3(throughput)} q/s | N/A |"
        )
    lines.extend(
        [
            "",
            "## 6. Core diagnostics",
            "",
            "| Model | Recall@10 | MRR@10 | nDCG@10 | Token F1 | ROUGE-L | Answerability accuracy | Abstain precision | Abstain recall | Abstain F1 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in CONFIGS:
        head = data["headline"][name]
        safety = data["answerability"][name]
        lines.append(
            f"| {name} | {f4(head['retrieval']['recall@10'])} | "
            f"{f4(head['retrieval']['mrr@10'])} | {f4(head['retrieval']['ndcg@10'])} | "
            f"{f4(head['answer_overlap']['token_f1'])} | {f4(head['answer_overlap']['rouge_l'])} | "
            f"{pct(safety['answerability_accuracy'])} | {pct(safety['abstain_precision'])} | "
            f"{pct(safety['abstain_recall'])} | {pct(safety['abstain_f1'])} |"
        )
    lines.extend(["", "## 7. Slice reporting", ""])
    lines.append(
        "Slice deltas are reranker minus RRF-only. CIs use the configured slice "
        f"bootstrap budget ({data['metadata']['slice_bootstrap_replicates']:,} "
        "replicates). Slices with fewer than 30 questions are exploratory."
    )
    lines.extend(
        [
            "",
            "| Dimension | Slice | n | Reranker | Δ Recall@10 (95% CI) | Δ MRR@10 (95% CI) | Δ nDCG@10 (95% CI) |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for dimension, groups in data["slices"].items():
        for value, group in groups.items():
            for name in RERANKERS:
                effects = group["vs_rrf"][name]
                lines.append(
                    f"| {dimension} | {value} | {group['count']} | {name} | "
                    f"{delta_ci(effects['recall@10'])} | {delta_ci(effects['mrr@10'])} | "
                    f"{delta_ci(effects['ndcg@10'])} |"
                )
    lines.extend(
        [
            "",
            f"Do not draw comparative conclusions from `multi_hop` "
            f"(n={data['slices']['category']['multi_hop']['count']} answerable cases), and do "
            "not promote the `hard` (n=1) or `cross_document` (n=12) groups to "
            "main evidence. The selected citation, legal-validity, and single-hop "
            "groups are larger but remain benchmark-specific.",
            "",
            "## 8. Annotation status",
            "",
            f"A blinded template with {data['annotations']['template_rows']:,} "
            "answerable system-question records was generated at "
            f"`{data['annotations']['template_path']}`. The template uses opaque "
            "system ids; the local key is stored separately for auditability.",
            "",
            "The following plan metrics remain unavailable until a blinded legal "
            "annotation or validated automatic judge is supplied: legal correctness, "
            "completeness, claim faithfulness, citation precision, citation recall, "
            "and claim-faithfulness annotations for the Pareto plot. The source "
            "records store only citation counts and citation markers, not explicit "
            "citation-to-chunk mappings.",
            "",
            "## 9. Figures",
            "",
            "- `forest_plot.svg`: paired retrieval effects and CIs; legal correctness is shown as unavailable.",
            "- `pareto_plot.svg`: nDCG@10 versus recorded total-latency p50; claim faithfulness is unavailable.",
            "",
            "## Reproducibility",
            "",
            f"- Seed: `{data['metadata']['seed']}`.",
            f"- Overall bootstrap replicates: `{data['metadata']['bootstrap_replicates']}`.",
            f"- Slice bootstrap replicates: `{data['metadata']['slice_bootstrap_replicates']}`.",
            "- Candidate source: `retrieval_cache/dense_all_hits.pkl` and `retrieval_cache/bm25_all_hits.pkl`.",
            "- Per-configuration source: `evaluation_runs/ablation3_reranker_v2/Rerank-*/`.",
            "- This analysis measures benchmark-sampling uncertainty; it does not measure run-to-run generator randomness.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_source_comparison() -> dict[str, dict[str, float | str]]:
    path = RUN_ROOT / "comparison.csv"
    result: dict[str, dict[str, float | str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            config = str(row["Config"])
            result[config] = {
                key: (value if key == "Config" else float(value))
                for key, value in row.items()
            }
    return result


def source_consistency(
    headline: dict[str, dict[str, Any]],
    answerability: dict[str, dict[str, Any]],
    latency: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Check recomputed headline values against the recorded aggregate CSV."""

    source = load_source_comparison()
    checks: list[dict[str, Any]] = []
    fields = (
        ("recall@10", lambda name: headline[name]["retrieval"]["recall@10"]),
        ("hit@10", lambda name: headline[name]["retrieval"]["hit@10"]),
        ("mrr@10", lambda name: headline[name]["retrieval"]["mrr@10"]),
        ("ndcg@10", lambda name: headline[name]["retrieval"]["ndcg@10"]),
        ("token_f1", lambda name: headline[name]["answer_overlap"]["token_f1"]),
        ("rouge_l", lambda name: headline[name]["answer_overlap"]["rouge_l"]),
        (
            "unanswerable_accuracy",
            lambda name: answerability[name]["recorded_unanswerable_accuracy_mean"],
        ),
        ("avg_reranker_latency", lambda name: latency[name]["reranker_mean_s"]),
        ("avg_total_latency", lambda name: latency[name]["total_mean_s"]),
    )
    max_abs_difference = 0.0
    for name, config_dir in CONFIGS.items():
        if config_dir not in source:
            raise ValueError(f"Missing {config_dir} in comparison.csv")
        for field, recompute in fields:
            recomputed = recompute(name)
            recorded = source[config_dir][field]
            if recomputed is None:
                raise ValueError(f"Cannot recompute {field} for {name}")
            difference = abs(float(recomputed) - float(recorded))
            max_abs_difference = max(max_abs_difference, difference)
            checks.append(
                {
                    "model": name,
                    "field": field,
                    "recomputed": float(recomputed),
                    "recorded": float(recorded),
                    "absolute_difference": difference,
                }
            )
    if max_abs_difference > 1e-4:
        raise ValueError(
            f"Recomputed metrics differ from comparison.csv by {max_abs_difference:.6f}"
        )
    return {
        "comparison_csv": str((RUN_ROOT / "comparison.csv").relative_to(ROOT)),
        "checks": len(checks),
        "max_abs_difference": max_abs_difference,
    }


def build_data(seed: int, bootstrap_replicates: int, slice_replicates: int) -> tuple[dict[str, Any], dict[str, dict[str, dict[str, Any]]], list[str]]:
    manifest_validation = validate_manifests()
    rows_by_name = {name: load_rows(config_dir) for name, config_dir in CONFIGS.items()}
    id_sets = {name: set(rows) for name, rows in rows_by_name.items()}
    common_ids = set.intersection(*id_sets.values())
    if any(ids != common_ids for ids in id_sets.values()):
        raise ValueError("Configurations do not have identical qa_id sets")
    ordered_ids = list(rows_by_name[PRIMARY_BASELINE])
    answerable_ids = [qa_id for qa_id in ordered_ids if is_answerable(rows_by_name[PRIMARY_BASELINE][qa_id])]
    if len(ordered_ids) != 500 or len(answerable_ids) != 400:
        raise ValueError(
            f"Expected 500 total and 400 answerable cases, found {len(ordered_ids)} and {len(answerable_ids)}"
        )
    for qa_id in ordered_ids:
        baseline = rows_by_name[PRIMARY_BASELINE][qa_id]
        for name, rows in rows_by_name.items():
            if bool(rows[qa_id].get("is_unanswerable")) != bool(baseline.get("is_unanswerable")):
                raise ValueError(f"Answerability label mismatch for {qa_id} in {name}")

    pools, pool_validation = build_candidate_pools(
        rows_by_name, rrf_k=60, limit=30
    )
    candidate_metrics = {
        name: candidate_controlled_metrics(rows, pools)
        for name, rows in rows_by_name.items()
    }
    case_values = build_case_metrics(rows_by_name, answerable_ids)
    headline = {name: headline_metrics(rows) for name, rows in rows_by_name.items()}
    answerability = {name: answerability_metrics(rows) for name, rows in rows_by_name.items()}
    latency = {
        name: latency_metrics(config_dir, len(rows))
        for name, config_dir in CONFIGS.items()
        for rows in [rows_by_name[name]]
    }
    source_validation = source_consistency(headline, answerability, latency)
    annotations_template, annotations_key, template_rows = write_annotation_files(
        rows_by_name, answerable_ids, seed=seed
    )

    metadata = {
        "analysis_script": str(Path(__file__).relative_to(Path.cwd()))
        if Path.cwd() in Path(__file__).resolve().parents
        else str(Path(__file__).resolve()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "bootstrap_replicates": bootstrap_replicates,
        "slice_bootstrap_replicates": slice_replicates,
        "primary_baseline": PRIMARY_BASELINE,
        "candidate_pool": "RRF top-30 reconstructed from shared dense/BM25 caches",
    }
    paired = paired_effects(
        case_values,
        answerable_ids=answerable_ids,
        replicates=bootstrap_replicates,
        seed=seed,
    )
    slices = slice_effects(
        case_values,
        rows_by_name,
        answerable_ids=answerable_ids,
        replicates=slice_replicates,
        seed=seed + 500000,
    )
    data: dict[str, Any] = {
        "metadata": metadata,
        "configuration_order": list(CONFIGS),
        "validation": {
            "same_qa_id_set": True,
            "total_cases": len(ordered_ids),
            "answerable_cases": len(answerable_ids),
            "unanswerable_cases": len(ordered_ids) - len(answerable_ids),
            "qa_id_count": len(common_ids),
            "all_configurations_have_500_cases": all(len(rows) == 500 for rows in rows_by_name.values()),
        },
        "manifest_validation": manifest_validation,
        "source_consistency": source_validation,
        "candidate_pool_validation": pool_validation,
        "candidate_controlled": candidate_metrics,
        "headline": headline,
        "paired_vs_rrf": paired,
        "answerability": answerability,
        "latency": latency,
        "slices": slices,
        "annotations": {
            "available": False,
            "reason": "No legal-judge labels, claim decomposition, or explicit citation-to-chunk mapping in source artifacts.",
            "template_path": str(annotations_template.relative_to(RUN_ROOT)),
            "key_path": str(annotations_key.relative_to(RUN_ROOT)),
            "template_rows": template_rows,
            "fields": [
                "legal_correctness_0_2",
                "completeness_0_2",
                "claim_faithfulness_fraction",
                "citation_precision_fraction",
                "citation_recall_fraction",
            ],
        },
        "unavailable_metrics": [
            "legal_correctness",
            "completeness",
            "claim_faithfulness",
            "citation_precision",
            "citation_recall",
            "peak_gpu_memory",
            "full_online_p95_latency",
        ],
        "source_comparison_csv": str((RUN_ROOT / "comparison.csv").relative_to(ROOT)),
    }
    return data, rows_by_name, answerable_ids


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    parser.add_argument("--slice-bootstrap-replicates", type=int, default=2000)
    args = parser.parse_args(argv)
    if args.bootstrap_replicates < 1 or args.slice_bootstrap_replicates < 1:
        parser.error("bootstrap replicate counts must be positive")

    data, _rows, _answerable_ids = build_data(
        args.seed, args.bootstrap_replicates, args.slice_bootstrap_replicates
    )
    json_path = RUN_ROOT / "paired_analysis.json"
    markdown_path = RUN_ROOT / "derived_metrics.md"
    forest_path = RUN_ROOT / "forest_plot.svg"
    pareto_path = RUN_ROOT / "pareto_plot.svg"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(data, markdown_path)
    write_svg_forest(data, forest_path)
    write_svg_pareto(data, pareto_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(f"Wrote {forest_path}")
    print(f"Wrote {pareto_path}")
    print(f"RRF alignment: {data['candidate_pool_validation']['rrf_recorded_top10_exact_matches']}/{data['candidate_pool_validation']['rrf_recorded_top10_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
