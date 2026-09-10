#!/usr/bin/env python3
"""Post-hoc analysis for the saved end-to-end LLM reasoning ablation.

The analysis is deliberately limited to the artifacts already saved under this
directory.  It does not call a model, rerun retrieval, or infer semantic
faithfulness from citation formatting.  The default output is suitable for the
current ``posthoc_metrics_plan.md`` and uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import random
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence


METRICS = ("exact_match", "token_f1", "rouge_l")
GROUP_FIELDS = ("category", "difficulty", "answer_type")
PAIR_MODEL_ORDER = (
    "gpt-4o-mini",
    "deepseek-v3.1-thinking",
    "glm-5",
    "qwen3-8b",
)
# The run directories are hand-organized, so the manifest remains authoritative
# for model identity.  These hints are used only to surface a naming mismatch
# in the generated provenance report rather than silently relabeling a run.
DIRECTORY_MODEL_HINTS = (
    ("4o-mini", "gpt-4o-mini"),
    ("deepseekv3.1-thinking", "deepseek-v3.1-thinking"),
    ("glm5", "glm-5"),
    ("qwen3-8b", "qwen3-8b"),
)
STRATUM_ORDER = ("support fully retrieved", "partial support retrieved", "no support retrieved")
EPSILON = 1e-12
SCHEMA_VERSION = "e2e-reasoning-posthoc-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Directory containing one subdirectory per saved run.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: ROOT/posthoc_results).",
    )
    parser.add_argument(
        "--bootstrap-reps",
        type=int,
        default=10_000,
        help="Number of paired bootstrap replicates (default: 10000).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Bootstrap seed.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected an object in {path}:{line_number}")
            rows.append(row)
    return rows


def is_success(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").strip().lower()
    if status in {"failed", "error", "skipped"}:
        return False
    if row.get("error") not in (None, "", {}):
        return False
    if status in {"success", "completed", "ok"}:
        return True
    # Keep the reader useful for older saved artifacts that did not persist a
    # status field, while never treating a failed generation as valid.
    return row.get("predicted_answer") is not None


def is_unanswerable(row: dict[str, Any]) -> bool:
    answer_type = str(row.get("answer_type") or "").strip().lower()
    category = str(row.get("category") or "").strip().lower()
    return answer_type == "unanswerable" or category == "unanswerable"


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return statistics.fmean(values) if values else None


def percentile(values: Sequence[float], q: float) -> float | None:
    """Linear percentile, matching the common inclusive interpolation rule."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def stable_seed(seed: int, key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return (seed ^ int.from_bytes(digest[:8], "big")) & ((1 << 63) - 1)


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    reps: int,
    seed: int,
) -> tuple[float | None, float | None]:
    """Return a percentile paired-bootstrap CI for the mean.

    A pure-Python implementation keeps this analysis runnable in the minimal
    project environment.  ``random.choices`` is used so the sampling loop is
    implemented in the standard library and remains quick for 400 cases.
    """
    if not values:
        return None, None
    if reps <= 0:
        raise ValueError("bootstrap reps must be positive")
    rng = random.Random(seed)
    values = [float(value) for value in values]
    n = len(values)
    boot_means: list[float] = []
    for _ in range(reps):
        boot_means.append(statistics.fmean(rng.choices(values, k=n)))
    return percentile(boot_means, 0.025), percentile(boot_means, 0.975)


def mcnemar_exact(base: Sequence[float], cot: Sequence[float]) -> float | None:
    """Two-sided exact McNemar p-value for paired binary observations."""
    if len(base) != len(cot) or not base:
        return None
    discordant_base_only = sum(1 for left, right in zip(base, cot) if left and not right)
    discordant_cot_only = sum(1 for left, right in zip(base, cot) if right and not left)
    discordant = discordant_base_only + discordant_cot_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(discordant_cot_only, discordant_base_only) + 1))
    p_value = 2.0 * tail / (2.0**discordant)
    return min(1.0, p_value)


def json_number(value: Any) -> Any:
    """Convert non-finite values to JSON null and preserve ordinary scalars."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(key): json_number(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_number(item) for item in value]
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(json_number(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})


def fmt(value: Any, digits: int = 2) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    return f"{number:.{digits}f}"


def fmt_pct(value: Any, digits: int = 2) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    return f"{100.0 * number:.{digits}f}%"


def fmt_pp(value: Any, digits: int = 2) -> str:
    number = safe_float(value)
    if number is None:
        return "—"
    sign = "+" if number >= 0 else ""
    return f"{sign}{100.0 * number:.{digits}f} pp"


def fmt_ci(low: Any, high: Any, *, percent: bool = True) -> str:
    if low is None or high is None:
        return "—"
    if percent:
        return f"[{100.0 * float(low):+.2f}, {100.0 * float(high):+.2f}] pp"
    return f"[{float(low):+.4f}, {float(high):+.4f}]"


def display_model(model: str) -> str:
    names = {
        "gpt-4o-mini": "GPT-4o-mini",
        "deepseek-v3.1-thinking": "DeepSeek-V3.1-Thinking",
        "glm-5": "GLM-5",
        "qwen3-8b": "Qwen3-8B",
    }
    return names.get(model, model)


def display_prompt(prompt: str) -> str:
    return "CoT" if prompt.lower() in {"reasoning", "cot", "structured_reasoning"} else "Base"


def error_reason(row: dict[str, Any]) -> str:
    error = row.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "")
    else:
        message = str(error or row.get("message") or "")
    lowered = message.lower()
    if "model_not_found" in lowered or "no longer supported" in lowered:
        return "model unavailable"
    if "insufficient_user_quota" in lowered or "quota" in lowered:
        return "quota"
    if "too many failed requests" in lowered or "429" in lowered:
        return "rate limit"
    if message:
        return message.split(":", 1)[0][:80]
    return "unknown failure"


def load_runs(root: Path) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or not (directory / "manifest.json").exists():
            continue
        prediction_path = directory / "e2e_predictions.jsonl"
        if not prediction_path.exists():
            continue
        manifest = read_json(directory / "manifest.json")
        rows = read_jsonl(prediction_path)
        latency = read_json(directory / "latency.json") if (directory / "latency.json").exists() else {}
        errors_path = directory / "errors.jsonl"
        error_rows = read_jsonl(errors_path) if errors_path.exists() else []
        model = str(manifest.get("generation_model") or manifest.get("resolved_config", {}).get("generation", {}).get("model") or directory.name)
        prompt = str(manifest.get("prompt_strategy") or manifest.get("resolved_config", {}).get("generation", {}).get("prompt_strategy") or "base")
        indexed: dict[str, dict[str, Any]] = {}
        duplicate_ids: list[str] = []
        for row in rows:
            qa_id = str(row.get("qa_id") or "")
            if not qa_id:
                raise ValueError(f"Missing qa_id in {prediction_path}")
            if qa_id in indexed:
                duplicate_ids.append(qa_id)
            indexed[qa_id] = row
        if duplicate_ids:
            raise ValueError(f"Duplicate qa_id(s) in {prediction_path}: {duplicate_ids[:3]}")
        completed = sum(1 for row in rows if is_success(row))
        skipped_rows = sum(1 for row in rows if str(row.get("status") or "").strip().lower() == "skipped")
        failed = len(rows) - completed - skipped_rows
        answerable_scheduled = sum(1 for row in rows if not is_unanswerable(row))
        unanswerable_scheduled = len(rows) - answerable_scheduled
        failed_rows = [
            row
            for row in rows
            if not is_success(row) and str(row.get("status") or "").strip().lower() != "skipped"
        ]
        # The errors artifact is the authoritative failure-stage/reason log;
        # fall back to prediction rows for older runs that did not persist it.
        stage_source = error_rows or failed_rows
        stage_counts = Counter(str(row.get("stage") or row.get("failed_stage") or "unknown") for row in stage_source)
        reason_counts = Counter(error_reason(row) for row in stage_source)
        runs[directory.name] = {
            "name": directory.name,
            "path": directory,
            "manifest": manifest,
            "rows": rows,
            "by_id": indexed,
            "latency": latency,
            "model": model,
            "prompt_strategy": prompt,
            "prompt": display_prompt(prompt),
            "scheduled": len(rows),
            "completed": completed,
            "failed": failed,
            "skipped": skipped_rows or int(manifest.get("skipped_case_count") or 0),
            "answerable_scheduled": answerable_scheduled,
            "unanswerable_scheduled": unanswerable_scheduled,
            "failure_stages": dict(sorted(stage_counts.items())),
            "failure_reasons": dict(sorted(reason_counts.items())),
            "error_artifact_count": len(error_rows),
            "fully_complete": failed == 0 and skipped_rows == 0 and len(rows) == int(manifest.get("total_input") or len(rows) or 0),
        }
    if not runs:
        raise ValueError(f"No saved run directories found under {root}")
    return runs


def pair_key(run: dict[str, Any]) -> tuple[int, str, str]:
    try:
        order = PAIR_MODEL_ORDER.index(run["model"])
    except ValueError:
        order = len(PAIR_MODEL_ORDER)
    return order, run["model"], run["prompt"]


def choose_pairs(runs: dict[str, dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    by_model: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for run in runs.values():
        by_model[run["model"]][run["prompt"]].append(run)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model, prompts in by_model.items():
        bases = sorted(prompts.get("Base", []), key=lambda item: item["name"])
        cots = sorted(prompts.get("CoT", []), key=lambda item: item["name"])
        if bases and cots:
            pairs.append((bases[0], cots[0]))
    pairs.sort(key=lambda pair: pair_key(pair[0]))
    return pairs


def data_quality_warnings(runs: dict[str, dict[str, Any]]) -> list[str]:
    """Return provenance warnings without changing manifest-derived identities."""
    warnings: list[str] = []
    for run in sorted(runs.values(), key=lambda item: item["name"]):
        lowered_name = run["name"].lower()
        expected_model = next(
            (expected for hint, expected in DIRECTORY_MODEL_HINTS if lowered_name.startswith(hint)),
            None,
        )
        if expected_model and run["model"] != expected_model:
            warnings.append(
                f"{run['name']}: directory name suggests `{expected_model}`, "
                f"but the manifest/resolved config declares `{run['model']}`; "
                "manifest metadata is used for analysis."
            )

    by_identity: dict[tuple[str, str], list[str]] = defaultdict(list)
    for run in runs.values():
        by_identity[(run["model"], run["prompt"])].append(run["name"])
    for (model, prompt), names in sorted(by_identity.items()):
        if len(names) > 1:
            warnings.append(
                f"Multiple run directories share the `{model}` / `{prompt}` identity: "
                f"{', '.join(sorted(names))}. The paired summary uses the lexicographically "
                "first Base/CoT directory; all runs remain in inventory and reliability outputs."
            )
    return warnings


def pair_rows(base: dict[str, Any], cot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for qa_id in sorted(set(base["by_id"]) & set(cot["by_id"])):
        left = base["by_id"][qa_id]
        right = cot["by_id"][qa_id]
        if not is_success(left) or not is_success(right):
            continue
        if is_unanswerable(left) or is_unanswerable(right):
            continue
        if any(safe_float(left.get(metric)) is None or safe_float(right.get(metric)) is None for metric in METRICS):
            continue
        item: dict[str, Any] = {
            "qa_id": qa_id,
            "category": left.get("category") or right.get("category") or "unknown",
            "difficulty": left.get("difficulty") or right.get("difficulty") or "unknown",
            "answer_type": left.get("answer_type") or right.get("answer_type") or "unknown",
            "base_context_recall": safe_float(left.get("context_recall@k")),
            "cot_context_recall": safe_float(right.get("context_recall@k")),
        }
        for metric in METRICS:
            item[f"base_{metric}"] = float(left[metric])
            item[f"cot_{metric}"] = float(right[metric])
            item[f"delta_{metric}"] = float(right[metric]) - float(left[metric])
        rows.append(item)
    return rows


def summary_for_values(
    values: Sequence[dict[str, Any]],
    metric: str,
    *,
    reps: int,
    seed: int,
    key: str,
) -> dict[str, Any]:
    base_values = [float(row[f"base_{metric}"]) for row in values]
    cot_values = [float(row[f"cot_{metric}"]) for row in values]
    deltas = [float(row[f"delta_{metric}"]) for row in values]
    wins = sum(delta > EPSILON for delta in deltas)
    ties = sum(abs(delta) <= EPSILON for delta in deltas)
    losses = sum(delta < -EPSILON for delta in deltas)
    ci_low, ci_high = bootstrap_mean_ci(deltas, reps=reps, seed=stable_seed(seed, key))
    output: dict[str, Any] = {
        "n": len(values),
        "base_mean": mean(base_values),
        "cot_mean": mean(cot_values),
        "delta_mean": mean(deltas),
        "delta_ci_low": ci_low,
        "delta_ci_high": ci_high,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "win_rate": wins / len(deltas) if deltas else None,
        "tie_rate": ties / len(deltas) if deltas else None,
        "loss_rate": losses / len(deltas) if deltas else None,
    }
    if metric == "exact_match":
        output["mcnemar_exact_p"] = mcnemar_exact(base_values, cot_values)
    return output


def paired_analysis(
    base: dict[str, Any],
    cot: dict[str, Any],
    *,
    reps: int,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    rows = pair_rows(base, cot)
    all_ids_equal = set(base["by_id"]) == set(cot["by_id"])
    fully_paired = base["fully_complete"] and cot["fully_complete"] and all_ids_equal
    metrics = {
        metric: summary_for_values(rows, metric, reps=reps, seed=seed, key=f"{base['model']}:{metric}")
        for metric in METRICS
    }
    groups: list[dict[str, Any]] = []
    for field in GROUP_FIELDS:
        names = sorted({str(row.get(field) or "unknown") for row in rows})
        for name in names:
            subset = [row for row in rows if str(row.get(field) or "unknown") == name]
            for metric in METRICS:
                result = summary_for_values(
                    subset,
                    metric,
                    reps=reps,
                    seed=seed,
                    key=f"{base['model']}:{field}:{name}:{metric}",
                )
                groups.append(
                    {
                        "model": base["model"],
                        "display_model": display_model(base["model"]),
                        "group_field": field,
                        "group": name,
                        "metric": metric,
                        **result,
                    }
                )
    pair = {
        "model": base["model"],
        "display_model": display_model(base["model"]),
        "base_run": base["name"],
        "cot_run": cot["name"],
        "base_scheduled": base["scheduled"],
        "cot_scheduled": cot["scheduled"],
        "base_completed": base["completed"],
        "cot_completed": cot["completed"],
        "base_failed": base["failed"],
        "cot_failed": cot["failed"],
        "shared_successful_answerable_n": len(rows),
        "all_question_ids_equal": all_ids_equal,
        "fully_paired": fully_paired,
        "interpretation": "primary paired inference" if fully_paired and base["model"] == "gpt-4o-mini" else "descriptive only",
        "metrics": metrics,
    }
    return pair, rows, groups


def evidence_stratum(context_recall: float | None) -> str:
    if context_recall is None:
        return "unknown support status"
    if context_recall >= 1.0 - EPSILON:
        return STRATUM_ORDER[0]
    if context_recall > EPSILON:
        return STRATUM_ORDER[1]
    return STRATUM_ORDER[2]


def evidence_analysis(
    rows: list[dict[str, Any]],
    *,
    reps: int,
    seed: int,
) -> tuple[list[dict[str, Any]], int]:
    strata: list[dict[str, Any]] = []
    context_mismatches = sum(
        1
        for row in rows
        if row.get("base_context_recall") is not None
        and row.get("cot_context_recall") is not None
        and abs(row["base_context_recall"] - row["cot_context_recall"]) > EPSILON
    )
    for index, name in enumerate(STRATUM_ORDER):
        subset = [row for row in rows if evidence_stratum(row.get("base_context_recall")) == name]
        record: dict[str, Any] = {"stratum": name, "n": len(subset), "metrics": {}}
        for metric in METRICS:
            record["metrics"][metric] = summary_for_values(
                subset,
                metric,
                reps=reps,
                seed=stable_seed(seed, f"evidence:{index}:{metric}"),
                key=f"evidence:{index}:{metric}",
            )
        strata.append(record)
    return strata, context_mismatches


def decision_from_saved_metric(row: dict[str, Any]) -> str:
    """Recover the run's persisted answer/refusal detector without re-scoring text.

    The historical detector was not persisted as a named function.  The
    binary ``unanswerable_accuracy`` field is its observable output: for an
    answerable case, 0 means template refusal; for an unanswerable case, 0
    means an attempted answer.  Failed rows remain ``failed``.
    """
    if not is_success(row):
        return "failed"
    score = safe_float(row.get("unanswerable_accuracy"))
    if score is None:
        return "unknown"
    if is_unanswerable(row):
        return "answer" if score < 0.5 else "refuse"
    return "refuse" if score < 0.5 else "answer"


def answerability_analysis(run: dict[str, Any]) -> dict[str, Any]:
    scheduled = run["rows"]
    valid = [row for row in scheduled if is_success(row)]
    counts = Counter()
    for row in scheduled:
        gold = "unanswerable" if is_unanswerable(row) else "answerable"
        decision = decision_from_saved_metric(row)
        counts[(gold, decision)] += 1
    answerable = [row for row in scheduled if not is_unanswerable(row)]
    unanswerable = [row for row in scheduled if is_unanswerable(row)]
    valid_answerable = [row for row in answerable if is_success(row)]
    valid_unanswerable = [row for row in unanswerable if is_success(row)]

    def rate(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    scheduled_correct = counts[("answerable", "answer")] + counts[("unanswerable", "refuse")]
    valid_counts = Counter(
        ("unanswerable" if is_unanswerable(row) else "answerable", decision_from_saved_metric(row))
        for row in valid
    )
    valid_correct = valid_counts[("answerable", "answer")] + valid_counts[("unanswerable", "refuse")]
    confusion = [
        {"gold": gold, "decision": decision, "count": counts[(gold, decision)]}
        for gold in ("answerable", "unanswerable")
        for decision in ("answer", "refuse", "failed")
    ]
    valid_only_confusion = [
        {"gold": gold, "decision": decision, "count": valid_counts[(gold, decision)]}
        for gold in ("answerable", "unanswerable")
        for decision in ("answer", "refuse")
    ]
    return {
        "run": run["name"],
        "model": run["model"],
        "display_model": display_model(run["model"]),
        "prompt": run["prompt"],
        "scheduled": len(scheduled),
        "valid": len(valid),
        "decision_source": "persisted unanswerable_accuracy detector output",
        "scheduled_metrics": {
            "unanswerable_recognition_rate": rate(counts[("unanswerable", "refuse")], len(unanswerable)),
            "answerable_non_refusal_rate": rate(counts[("answerable", "answer")], len(answerable)),
            "false_refusal_rate": rate(counts[("answerable", "refuse")], len(answerable)),
            "overall_template_decision_accuracy": rate(scheduled_correct, len(scheduled)),
        },
        "valid_only_metrics": {
            "unanswerable_recognition_rate": rate(valid_counts[("unanswerable", "refuse")], len(valid_unanswerable)),
            "answerable_non_refusal_rate": rate(valid_counts[("answerable", "answer")], len(valid_answerable)),
            "false_refusal_rate": rate(valid_counts[("answerable", "refuse")], len(valid_answerable)),
            "overall_template_decision_accuracy": rate(valid_correct, len(valid)),
        },
        "confusion": confusion,
        "valid_only_confusion": valid_only_confusion,
    }


def citation_analysis(run: dict[str, Any]) -> dict[str, Any]:
    scheduled = [row for row in run["rows"] if not is_unanswerable(row)]
    valid = [row for row in scheduled if is_success(row)]

    def citation_metric(row: dict[str, Any], key: str) -> float | None:
        metrics = row.get("citation_metrics")
        if not isinstance(metrics, dict):
            return None
        return safe_float(metrics.get(key))

    def metric_values(rows: Iterable[dict[str, Any]], key: str) -> list[float]:
        return [value for row in rows if (value := citation_metric(row, key)) is not None]

    citation_counts = [citation_metric(row, "citation_count") or 0.0 for row in valid]
    invalid_counts = [citation_metric(row, "invalid_citation_count") or 0.0 for row in valid]
    all_markers = sum(citation_counts)
    invalid_markers = sum(invalid_counts)
    coverage = metric_values(valid, "structural_citation_coverage")
    unique = [citation_metric(row, "unique_cited_source_count") or 0.0 for row in valid]
    presence_count = sum(count > 0 for count in citation_counts)
    return {
        "run": run["name"],
        "model": run["model"],
        "display_model": display_model(run["model"]),
        "prompt": run["prompt"],
        "scheduled_answerable": len(scheduled),
        "valid_answerable": len(valid),
        "citation_presence_rate": presence_count / len(valid) if valid else None,
        "citation_presence_count": presence_count,
        "structural_coverage_mean": mean(coverage),
        "structural_coverage_n": len(coverage),
        "mean_unique_cited_sources": mean(unique),
        "invalid_marker_count": int(invalid_markers),
        "total_marker_count": int(all_markers),
        "invalid_marker_rate": invalid_markers / all_markers if all_markers else 0.0,
        "cases_with_invalid_citations": sum(count > 0 for count in invalid_counts),
        "cases_with_no_valid_citation": sum(count <= 0 for count in citation_counts),
        "claim_entailment_available": False,
    }


def latency_analysis(run: dict[str, Any]) -> dict[str, Any]:
    stages = run.get("latency", {}).get("stages", {})
    result: dict[str, Any] = {}
    for stage_name in ("generation", "total"):
        stage = stages.get(stage_name)
        if not isinstance(stage, dict):
            result[stage_name] = None
            continue
        # Saved latency artifacts are milliseconds; report seconds.
        result[stage_name] = {
            "count": stage.get("count"),
            "mean_s": safe_float(stage.get("mean")) / 1000.0 if safe_float(stage.get("mean")) is not None else None,
            "p50_s": safe_float(stage.get("median")) / 1000.0 if safe_float(stage.get("median")) is not None else None,
            "p95_s": safe_float(stage.get("p95")) / 1000.0 if safe_float(stage.get("p95")) is not None else None,
        }
    return result


def reliability_analysis(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run": run["name"],
        "model": run["model"],
        "display_model": display_model(run["model"]),
        "prompt": run["prompt"],
        "scheduled": run["scheduled"],
        "completed": run["completed"],
        "failed": run["failed"],
        "skipped": run["skipped"],
        "error_artifact_count": run["error_artifact_count"],
        "completion_rate": run["completed"] / run["scheduled"] if run["scheduled"] else None,
        "failure_rate": run["failed"] / run["scheduled"] if run["scheduled"] else None,
        "failure_stages": run["failure_stages"],
        "failure_reasons": run["failure_reasons"],
        "latency": latency_analysis(run),
    }


def compact_run_rows(runs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in sorted(runs.values(), key=pair_key):
        metrics_path = run["path"] / "e2e_metrics.json"
        saved = read_json(metrics_path) if metrics_path.exists() else {}
        overall = saved.get("overall") if isinstance(saved.get("overall"), dict) else {}
        citation = citation_analysis(run)
        latency = latency_analysis(run)
        rows.append(
            {
                "run": run["name"],
                "model": run["model"],
                "prompt": run["prompt"],
                "scheduled": run["scheduled"],
                "completed": run["completed"],
                "failed": run["failed"],
                "completion_rate": run["completed"] / run["scheduled"] if run["scheduled"] else None,
                "exact_match": safe_float(overall.get("exact_match")),
                "token_f1": safe_float(overall.get("token_f1")),
                "rouge_l": safe_float(overall.get("rouge_l")),
                "answerability_decision_accuracy": safe_float(overall.get("unanswerable_accuracy")),
                "citation_presence_rate": citation["citation_presence_rate"],
                "structural_citation_coverage": citation["structural_coverage_mean"],
                "mean_unique_cited_sources": citation["mean_unique_cited_sources"],
                "generation_p50_s": (latency.get("generation") or {}).get("p50_s") if latency.get("generation") else None,
                "generation_p95_s": (latency.get("generation") or {}).get("p95_s") if latency.get("generation") else None,
                "total_p50_s": (latency.get("total") or {}).get("p50_s") if latency.get("total") else None,
                "total_p95_s": (latency.get("total") or {}).get("p95_s") if latency.get("total") else None,
            }
        )
    return rows


def csv_rows_for_pairs(pairs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        for metric, result in pair["metrics"].items():
            rows.append({"model": pair["model"], "display_model": pair["display_model"], "base_run": pair["base_run"], "cot_run": pair["cot_run"], "fully_paired": pair["fully_paired"], "interpretation": pair["interpretation"], "metric": metric, **result})
    return rows


def csv_rows_for_evidence(pairs: Sequence[dict[str, Any]], primary_model: str) -> list[dict[str, Any]]:
    for pair in pairs:
        if pair["model"] == primary_model:
            return [
                {
                    "model": primary_model,
                    "stratum": record["stratum"],
                    "n": record["n"],
                    "metric": metric,
                    **values,
                }
                for record in pair.get("evidence_strata", [])
                for metric, values in record["metrics"].items()
            ]
    return []


def html_escape(value: Any) -> str:
    return html.escape(str(value))


def svg_text(x: float, y: float, text: str, *, size: int = 12, anchor: str = "start", fill: str = "#253047", weight: str = "400") -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" font-size="{size}px" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}">{html_escape(text)}</text>'


def svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        svg_text(24, 30, title, size=17, weight="700"),
    ]


def write_token_delta_svg(path: Path, rows: Sequence[dict[str, Any]], strata: Sequence[dict[str, Any]]) -> None:
    width, height = 980, 560
    lines = svg_header(width, height, "GPT-4o-mini paired Token-F1 deltas (CoT − Base)")
    chart_left, chart_top, chart_width, chart_height = 70, 70, 870, 390
    deltas = sorted(float(row["delta_token_f1"]) for row in rows)
    if not deltas:
        lines.append(svg_text(width / 2, height / 2, "No paired cases", anchor="middle"))
    else:
        bins = 20
        low = min(deltas)
        high = max(deltas)
        if abs(high - low) < EPSILON:
            low -= 0.01
            high += 0.01
        step = (high - low) / bins
        counts = [0] * bins
        for delta in deltas:
            index = min(bins - 1, max(0, int((delta - low) / step)))
            counts[index] += 1
        maximum = max(counts) or 1
        zero_x = chart_left + (0 - low) / (high - low) * chart_width
        lines.append(f'<line x1="{chart_left}" y1="{chart_top + chart_height}" x2="{chart_left + chart_width}" y2="{chart_top + chart_height}" stroke="#718096"/>')
        lines.append(f'<line x1="{zero_x:.1f}" y1="{chart_top}" x2="{zero_x:.1f}" y2="{chart_top + chart_height}" stroke="#b83280" stroke-dasharray="5,4"/>')
        for index, count in enumerate(counts):
            x = chart_left + index * chart_width / bins + 1
            bar_width = chart_width / bins - 2
            bar_height = count / maximum * (chart_height - 30)
            y = chart_top + chart_height - bar_height
            fill = "#3182ce" if low + (index + 0.5) * step >= 0 else "#dd6b20"
            lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{fill}" opacity="0.85"/>')
        lines.extend(
            [
                svg_text(chart_left, chart_top + chart_height + 25, f"{low:.3f}", size=10),
                svg_text(zero_x, chart_top + chart_height + 25, "0", size=10, anchor="middle"),
                svg_text(chart_left + chart_width, chart_top + chart_height + 25, f"{high:.3f}", size=10, anchor="end"),
                svg_text(chart_left + chart_width / 2, chart_top + chart_height + 48, "Token-F1 delta", size=11, anchor="middle"),
                svg_text(chart_left - 12, chart_top + 10, str(maximum), size=10, anchor="end"),
                svg_text(chart_left - 12, chart_top + chart_height, "0", size=10, anchor="end"),
            ]
        )
        legend_y = chart_top + chart_height + 85
        lines.append('<rect x="70" y="%d" width="12" height="12" fill="#3182ce"/>' % legend_y)
        lines.append(svg_text(88, legend_y + 11, "CoT gain", size=11))
        lines.append('<rect x="190" y="%d" width="12" height="12" fill="#dd6b20"/>' % legend_y)
        lines.append(svg_text(208, legend_y + 11, "CoT loss", size=11))
        lines.append(svg_text(460, legend_y + 11, f"n={len(deltas)} answerable paired cases", size=11))
        summary_y = legend_y + 42
        for index, record in enumerate(strata):
            metric = record["metrics"]["token_f1"]
            text = f"{record['stratum']}: n={record['n']}, Δ={fmt_pp(metric['delta_mean'])}"
            lines.append(svg_text(70 + (index % 2) * 430, summary_y + (index // 2) * 20, text, size=10))
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_win_tie_loss_svg(path: Path, group_rows: Sequence[dict[str, Any]], *, model: str) -> None:
    selected = [row for row in group_rows if row["metric"] == "token_f1" and row["group_field"] in {"category", "difficulty"}]
    width, height = 980, 560
    lines = svg_header(width, height, f"{display_model(model)} Token-F1 win/tie/loss by slice")
    x0, y0, bar_width, bar_gap = 260, 78, 570, 34
    rows_by_field: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        rows_by_field[row["group_field"]].append(row)
    row_index = 0
    colors = {"wins": "#3182ce", "ties": "#a0aec0", "losses": "#dd6b20"}
    for field in ("category", "difficulty"):
        values = sorted(rows_by_field.get(field, []), key=lambda item: str(item["group"]))
        if not values:
            continue
        lines.append(svg_text(40, y0 + row_index * bar_gap - 9, field.replace("_", " ").title(), size=12, weight="700"))
        row_index += 1
        for row in values:
            y = y0 + row_index * bar_gap
            lines.append(svg_text(x0 - 12, y + 13, str(row["group"]), size=11, anchor="end"))
            left = x0
            for key in ("wins", "ties", "losses"):
                proportion = (row[key] or 0) / row["n"] if row["n"] else 0
                segment = bar_width * proportion
                lines.append(f'<rect x="{left:.1f}" y="{y:.1f}" width="{segment:.1f}" height="20" fill="{colors[key]}"/>')
                left += segment
            lines.append(svg_text(x0 + bar_width + 10, y + 13, f"n={row['n']}", size=10))
            row_index += 1
    lines.append(svg_text(x0, y0 + row_index * bar_gap + 25, "CoT win/tie/loss share", size=11))
    legend_y = y0 + row_index * bar_gap + 52
    left = x0
    for key, label in (("wins", "win"), ("ties", "tie"), ("losses", "loss")):
        lines.append(f'<rect x="{left}" y="{legend_y}" width="12" height="12" fill="{colors[key]}"/>')
        lines.append(svg_text(left + 18, legend_y + 11, label, size=11))
        left += 80
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_confusion_svg(
    path: Path,
    matrices: Sequence[tuple[str, Sequence[dict[str, Any]]]],
    *,
    model: str,
) -> None:
    width, height = max(620, 470 * len(matrices)), 390
    lines = svg_header(width, height, f"Template-based decision matrices: {display_model(model)}")
    y0, cell_w, cell_h = 100, 100, 70
    columns = ("answer", "refuse", "failed")
    gold_rows = ("answerable", "unanswerable")
    for matrix_index, (prompt, decision_rows) in enumerate(matrices):
        counts = {(row["gold"], row["decision"]): int(row["count"]) for row in decision_rows}
        x0 = 95 + matrix_index * 470
        lines.append(svg_text(x0 + 1.5 * cell_w, y0 - 37, prompt, size=13, anchor="middle", weight="700"))
        lines.append(svg_text(x0 + 1.5 * cell_w, y0 - 20, "Saved decision", size=11, anchor="middle"))
        for index, column in enumerate(columns):
            lines.append(svg_text(x0 + (index + 0.5) * cell_w, y0 - 5, column, size=11, anchor="middle"))
        max_count = max(counts.values() or [1])
        for r_index, gold in enumerate(gold_rows):
            y = y0 + r_index * cell_h
            lines.append(svg_text(x0 - 15, y + cell_h / 2 + 4, gold, size=11, anchor="end"))
            for c_index, column in enumerate(columns):
                count = counts.get((gold, column), 0)
                intensity = 0.15 + 0.75 * count / max_count
                color = f"rgb({int(220 - 100 * intensity)},{int(235 - 80 * intensity)},{int(250 - 40 * intensity)})"
                x = x0 + c_index * cell_w
                lines.append(f'<rect x="{x}" y="{y}" width="{cell_w - 3}" height="{cell_h - 3}" fill="{color}" stroke="white"/>')
                lines.append(svg_text(x + cell_w / 2, y + cell_h / 2 + 5, str(count), size=18, anchor="middle", weight="700"))
    lines.append(svg_text(width / 2, y0 + 2 * cell_h + 38, "Counts include failed rows; valid-only matrices are in JSON/CSV.", size=10, anchor="middle", fill="#4a5568"))
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] + ["---:"] * (len(headers) - 1)) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def build_report(
    *,
    root: Path,
    out_dir: Path,
    runs: dict[str, dict[str, Any]],
    pairs: Sequence[dict[str, Any]],
    reliability: Sequence[dict[str, Any]],
    decisions: Sequence[dict[str, Any]],
    citations: Sequence[dict[str, Any]],
    evidence_mismatches: int,
    quality_warnings: Sequence[str],
    bootstrap_reps: int,
    seed: int,
) -> str:
    primary = next((pair for pair in pairs if pair["model"] == "gpt-4o-mini"), None)
    lines: list[str] = [
        "# Post-hoc Evaluation: LLM Reasoning Ablation",
        "",
        "> Generated from the saved run artifacts; no model call, retrieval rerun, or new annotation was used.",
        "",
        "## Scope and claim boundary",
        "",
        f"This report analyzes `{len(runs)}` saved runs under `{root}`. The primary paired inference is GPT-4o-mini Base versus CoT; other model pairs remain descriptive, with incomplete cells and identity/provenance checks exposed below. Paired bootstrap intervals use {bootstrap_reps:,} replicates (seed {seed}).",
        "",
        "The historical outputs contain final answers, retrieval context, structural citation metadata, and lexical metrics, but no claim annotations, semantic entailment labels, structured justification, raw CoT, or reasoning-token accounting. Accordingly, this report does **not** claim legal correctness, claim faithfulness, citation entailment, refusal quality, or faithful latent reasoning.",
    ]
    if quality_warnings:
        lines.extend(
            [
                "",
                "## Data-integrity notes",
                "",
                "The following provenance checks found naming or identity ambiguities. They are reported rather than repaired automatically:",
                "",
                *[f"- {warning}" for warning in quality_warnings],
            ]
        )
    lines.extend(["", "## Run inventory", ""])
    inventory_rows = []
    for run in reliability:
        inventory_rows.append(
            [
                f"{run['display_model']} / {run['prompt']}",
                f"{run['completed']} / {run['scheduled']}",
                run["failed"],
                fmt_pct(run["completion_rate"]),
                ", ".join(f"{key}: {value}" for key, value in run["failure_reasons"].items()) or "—",
            ]
        )
    lines.extend(markdown_table(["Condition", "Valid / scheduled", "Failures", "Completion", "Failure reason"], inventory_rows))
    lines.extend(
        [
            "",
            "Failed generations are retained in scheduled-denominator reliability and decision views. Incomplete rows are not silently treated as lexical failures in the paired-quality tables; those tables use the exact successful answerable intersection and expose its `n`.",
            "",
            "## 1. Primary paired comparison: GPT-4o-mini",
            "",
        ]
    )
    if primary is None:
        lines.append("The GPT-4o-mini Base/CoT pair was not found.")
    else:
        metric_rows = []
        for metric in METRICS:
            result = primary["metrics"][metric]
            metric_rows.append(
                [
                    metric.replace("_", " ").title(),
                    fmt_pct(result["base_mean"]),
                    fmt_pct(result["cot_mean"]),
                    fmt_pp(result["delta_mean"]),
                    fmt_ci(result["delta_ci_low"], result["delta_ci_high"]),
                    result["n"],
                ]
            )
        lines.extend(markdown_table(["Metric", "Base", "CoT", "CoT − Base", "95% paired CI", "n"], metric_rows))
        lines.extend(["", "| Metric | CoT win | Tie | CoT loss | McNemar exact p (EM only) |", "| --- | ---: | ---: | ---: | ---: |"])
        for metric in METRICS:
            result = primary["metrics"][metric]
            p_value = fmt(result.get("mcnemar_exact_p"), 4) if metric == "exact_match" else "—"
            lines.append(f"| {metric.replace('_', ' ').title()} | {result['wins']} ({fmt_pct(result['win_rate'])}) | {result['ties']} ({fmt_pct(result['tie_rate'])}) | {result['losses']} ({fmt_pct(result['loss_rate'])}) | {p_value} |")
        lines.extend(
            [
                "",
                f"The exact successful answerable intersection is `n={primary['shared_successful_answerable_n']}`; both cells are fully paired: `{primary['fully_paired']}`.",
                "",
                "### Evidence-availability stratification",
                "",
                "`context_recall@k` is used only to stratify the fixed retrieved context. It is not interpreted as a prompt-improvable outcome. The GPT pair has " + str(evidence_mismatches) + " context-recall mismatches across matched cases.",
                "",
            ]
        )
        evidence_rows = []
        for record in primary.get("evidence_strata", []):
            em = record["metrics"]["exact_match"]
            f1 = record["metrics"]["token_f1"]
            rouge = record["metrics"]["rouge_l"]
            evidence_rows.append(
                [
                    record["stratum"],
                    record["n"],
                    fmt_pct(em["base_mean"]),
                    fmt_pct(em["cot_mean"]),
                    fmt_pp(em["delta_mean"]),
                    fmt_pct(f1["base_mean"]),
                    fmt_pct(f1["cot_mean"]),
                    fmt_pp(f1["delta_mean"]),
                    fmt_pct(rouge["base_mean"]),
                    fmt_pct(rouge["cot_mean"]),
                    fmt_pp(rouge["delta_mean"]),
                ]
            )
        lines.extend(markdown_table(["Evidence stratum", "n", "Base EM", "CoT EM", "Δ EM", "Base F1", "CoT F1", "Δ F1", "Base ROUGE-L", "CoT ROUGE-L", "Δ ROUGE-L"], evidence_rows))
        lines.extend(
            [
                "",
                "The saved data reproduce the planned strata (fully present, partial, absent). They show observable answer behavior conditional on retrieved support, not claim-level faithfulness.",
                "",
            ]
        )

    lines.extend(["## 2. Answerability decision behavior", "", "The saved `unanswerable_accuracy` field is relabeled here as **template-based answerability decision accuracy**. It detects answer/refusal format behavior; it is not a semantic refusal-quality measure. Clarification cannot be recovered from the historical final-answer records.", ""])
    decision_rows = []
    for decision in decisions:
        scheduled = decision["scheduled_metrics"]
        valid = decision["valid_only_metrics"]
        decision_rows.append(
            [
                f"{decision['display_model']} / {decision['prompt']}",
                fmt_pct(scheduled["unanswerable_recognition_rate"]),
                fmt_pct(scheduled["answerable_non_refusal_rate"]),
                fmt_pct(scheduled["false_refusal_rate"]),
                fmt_pct(scheduled["overall_template_decision_accuracy"]),
                fmt_pct(valid["overall_template_decision_accuracy"]),
            ]
        )
    lines.extend(markdown_table(["Condition", "Unanswerable recognition", "Answerable non-refusal", "False refusal", "Overall (scheduled)", "Overall (valid only)"], decision_rows))
    lines.extend(["", "For the complete GPT pair, the answerability matrix is:", ""])
    if primary is not None:
        primary_decisions = [item for item in decisions if item["run"] in {primary["base_run"], primary["cot_run"]}]
        matrix_rows = []
        for decision in primary_decisions:
            counts = {(row["gold"], row["decision"]): row["count"] for row in decision["confusion"]}
            matrix_rows.extend(
                [
                    [f"{decision['prompt']}", "answerable", counts.get(("answerable", "answer"), 0), counts.get(("answerable", "refuse"), 0), counts.get(("answerable", "failed"), 0)],
                    [f"{decision['prompt']}", "unanswerable", counts.get(("unanswerable", "answer"), 0), counts.get(("unanswerable", "refuse"), 0), counts.get(("unanswerable", "failed"), 0)],
                ]
            )
        lines.extend(markdown_table(["Prompt", "Gold", "Answer", "Refuse", "Failed"], matrix_rows))
        lines.append("")

    lines.extend(["## 3. Citation discipline (structural only)", "", "Citation metrics below describe marker presence and parser coverage. They do not establish that a cited passage entails a claim.", ""])
    citation_rows = []
    for citation in citations:
        citation_rows.append(
            [
                f"{citation['display_model']} / {citation['prompt']}",
                f"{citation['valid_answerable']} / {citation['scheduled_answerable']}",
                fmt_pct(citation["citation_presence_rate"]),
                fmt_pct(citation["structural_coverage_mean"]),
                fmt(citation["mean_unique_cited_sources"]),
                f"{citation['invalid_marker_count']} / {citation['total_marker_count']}",
            ]
        )
    lines.extend(markdown_table(["Condition", "Valid answerable / scheduled", "Citation presence", "Structural coverage", "Mean unique sources", "Invalid / all markers"], citation_rows))
    lines.extend(["", "## 4. Reliability and efficiency", ""])
    latency_rows = []
    for run in reliability:
        generation = run["latency"].get("generation") or {}
        total = run["latency"].get("total") or {}
        latency_rows.append(
            [
                f"{run['display_model']} / {run['prompt']}",
                f"{run['completed']} / {run['scheduled']}",
                f"{generation.get('p50_s', '—'):.2f} / {generation.get('p95_s', '—'):.2f}" if generation.get("p50_s") is not None and generation.get("p95_s") is not None else "—",
                f"{total.get('p50_s', '—'):.2f} / {total.get('p95_s', '—'):.2f}" if total.get("p50_s") is not None and total.get("p95_s") is not None else "—",
                ", ".join(f"{key}: {value}" for key, value in run["failure_stages"].items()) or "—",
            ]
        )
    lines.extend(markdown_table(["Condition", "Valid / scheduled", "Generation p50 / p95 (s)", "Total p50 / p95 (s)", "Failure stage"], latency_rows))
    lines.extend(
        [
            "",
            "Token counts, provider reasoning-token metadata, and cost are not present in the saved records. The latency artifacts include means and percentiles; p50/p95 are used here to expose the long tail.",
            "",
            "## 5. Descriptive model pairs",
            "",
            "The following pairs are exported in `paired_metrics.csv` and `paired_group_deltas.csv`. They are not primary prompt effects unless both cells contain the same complete question set with no failures.",
            "",
        ]
    )
    pair_rows_md = []
    for pair in pairs:
        f1 = pair["metrics"]["token_f1"]
        pair_rows_md.append([pair["display_model"], f"{pair['base_completed']}/{pair['base_scheduled']}", f"{pair['cot_completed']}/{pair['cot_scheduled']}", f1["n"], fmt_pp(f1["delta_mean"]), pair["interpretation"]])
    lines.extend(markdown_table(["Model", "Base valid", "CoT valid", "Paired n", "Δ Token F1", "Interpretation"], pair_rows_md))
    lines.extend(
        [
            "",
            "## Figures and machine-readable outputs",
            "",
            "- [Paired Token-F1 delta histogram](paired_token_f1_delta.svg)",
            "- [Win/tie/loss slice bars](win_tie_loss.svg)",
            "- [Template decision matrix](refusal_confusion.svg)",
            "- `posthoc_analysis.json`: complete analysis object and provenance",
            "- `paired_case_deltas.csv`: one row per successful paired answerable case",
            "- `paired_metrics.csv`: aggregate paired deltas and CIs",
            "- `paired_group_deltas.csv`: category/difficulty/answer-type slices",
            "- `evidence_strata.csv`, `answerability_decisions.csv`, `citation_metrics.csv`, `run_reliability.csv`: appendix tables",
            "",
            "## Bounded conclusion",
            "",
            "Under fixed retrieved context, the saved GPT-4o-mini pair characterizes observable Base-versus-CoT output behavior, including lexical deltas, template-based decision behavior, structural citation formatting, and latency. It cannot demonstrate superior or inferior latent reasoning, legal correctness, claim faithfulness, citation entailment, or refusal quality. Provider-failed and partial cells remain descriptive until rerun to completion.",
            "",
            f"Generated by `analyze_posthoc.py`; bootstrap replicates={bootstrap_reps}, seed={seed}, output directory `{out_dir}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if args.bootstrap_reps <= 0:
        raise SystemExit("--bootstrap-reps must be positive")
    root = args.root.resolve()
    out_dir = (args.out_dir or root / "posthoc_results").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = load_runs(root)
    quality_warnings = data_quality_warnings(runs)
    selected_pairs = choose_pairs(runs)
    pair_summaries: list[dict[str, Any]] = []
    all_group_rows: list[dict[str, Any]] = []
    case_rows_by_model: dict[str, list[dict[str, Any]]] = {}
    evidence_mismatches = 0
    for base, cot in selected_pairs:
        pair, case_rows, group_rows = paired_analysis(base, cot, reps=args.bootstrap_reps, seed=args.seed)
        pair_summaries.append(pair)
        all_group_rows.extend(group_rows)
        case_rows_by_model[pair["model"]] = case_rows
        if pair["model"] == "gpt-4o-mini":
            strata, mismatches = evidence_analysis(case_rows, reps=args.bootstrap_reps, seed=args.seed)
            pair["evidence_strata"] = strata
            evidence_mismatches = mismatches

    reliability = [reliability_analysis(run) for run in sorted(runs.values(), key=pair_key)]
    decisions = [answerability_analysis(run) for run in sorted(runs.values(), key=pair_key)]
    citations = [citation_analysis(run) for run in sorted(runs.values(), key=pair_key)]
    primary_model = "gpt-4o-mini"
    primary_cases = case_rows_by_model.get(primary_model, [])
    primary_pair = next((pair for pair in pair_summaries if pair["model"] == primary_model), None)

    # Machine-readable artifacts.
    case_csv_fields = ["model", "qa_id", "category", "difficulty", "answer_type", "base_context_recall", "cot_context_recall", *[field for metric in METRICS for field in (f"base_{metric}", f"cot_{metric}", f"delta_{metric}")]]
    case_csv_rows = [{"model": primary_model, **row} for row in primary_cases]
    for model, rows in case_rows_by_model.items():
        if model == primary_model:
            continue
        case_csv_rows.extend({"model": model, **row} for row in rows)
    write_csv(out_dir / "paired_case_deltas.csv", case_csv_rows, case_csv_fields)
    write_csv(out_dir / "paired_metrics.csv", csv_rows_for_pairs(pair_summaries), ["model", "display_model", "base_run", "cot_run", "fully_paired", "interpretation", "metric", "n", "base_mean", "cot_mean", "delta_mean", "delta_ci_low", "delta_ci_high", "wins", "ties", "losses", "win_rate", "tie_rate", "loss_rate", "mcnemar_exact_p"])
    write_csv(out_dir / "paired_group_deltas.csv", all_group_rows, ["model", "display_model", "group_field", "group", "metric", "n", "base_mean", "cot_mean", "delta_mean", "delta_ci_low", "delta_ci_high", "wins", "ties", "losses", "win_rate", "tie_rate", "loss_rate", "mcnemar_exact_p"])
    evidence_csv_rows = []
    if primary_pair:
        for record in primary_pair.get("evidence_strata", []):
            for metric, values in record["metrics"].items():
                evidence_csv_rows.append({"model": primary_model, "stratum": record["stratum"], "n": record["n"], "metric": metric, **values})
    write_csv(out_dir / "evidence_strata.csv", evidence_csv_rows, ["model", "stratum", "n", "metric", "base_mean", "cot_mean", "delta_mean", "delta_ci_low", "delta_ci_high", "wins", "ties", "losses", "win_rate", "tie_rate", "loss_rate", "mcnemar_exact_p"])
    write_csv(out_dir / "answerability_decisions.csv", [
        {"run": decision["run"], "model": decision["model"], "display_model": decision["display_model"], "prompt": decision["prompt"], "view": view, "metric": metric, "value": value}
        for decision in decisions
        for view, metrics in (("scheduled", decision["scheduled_metrics"]), ("valid_only", decision["valid_only_metrics"]))
        for metric, value in metrics.items()
    ] + [
        {"run": decision["run"], "model": decision["model"], "display_model": decision["display_model"], "prompt": decision["prompt"], "view": "scheduled_confusion", "metric": f"{row['gold']}__{row['decision']}", "value": row["count"]}
        for decision in decisions for row in decision["confusion"]
    ], ["run", "model", "display_model", "prompt", "view", "metric", "value"])
    write_csv(out_dir / "citation_metrics.csv", citations, ["run", "model", "display_model", "prompt", "scheduled_answerable", "valid_answerable", "citation_presence_rate", "citation_presence_count", "structural_coverage_mean", "structural_coverage_n", "mean_unique_cited_sources", "invalid_marker_count", "total_marker_count", "invalid_marker_rate", "cases_with_invalid_citations", "cases_with_no_valid_citation", "claim_entailment_available"])
    write_csv(out_dir / "run_reliability.csv", compact_run_rows(runs), ["run", "model", "prompt", "scheduled", "completed", "failed", "completion_rate", "exact_match", "token_f1", "rouge_l", "answerability_decision_accuracy", "citation_presence_rate", "structural_citation_coverage", "mean_unique_cited_sources", "generation_p50_s", "generation_p95_s", "total_p50_s", "total_p95_s"])

    if primary_pair:
        write_token_delta_svg(out_dir / "paired_token_f1_delta.svg", primary_cases, primary_pair.get("evidence_strata", []))
        write_win_tie_loss_svg(out_dir / "win_tie_loss.svg", [row for row in all_group_rows if row["model"] == primary_model], model=primary_model)
        primary_decisions = [
            (decision["prompt"], decision["confusion"])
            for decision in decisions
            if decision["run"] in {primary_pair["base_run"], primary_pair["cot_run"]}
        ]
        if primary_decisions:
            write_confusion_svg(out_dir / "refusal_confusion.svg", primary_decisions, model=primary_model)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "root": str(root),
        "output_directory": str(out_dir),
        "data_quality_warnings": quality_warnings,
        "bootstrap": {"replicates": args.bootstrap_reps, "seed": args.seed, "ci": "percentile 95%"},
        "claim_boundary": {
            "uses_only_saved_artifacts": True,
            "semantic_claim_faithfulness_available": False,
            "citation_entailment_available": False,
            "legal_correctness_annotation_available": False,
            "structured_justification_available": False,
            "reasoning_token_accounting_available": False,
            "primary_pair": "gpt-4o-mini Base vs CoT",
        },
        "runs": reliability,
        "answerability": decisions,
        "citations": citations,
        "pairs": pair_summaries,
        "evidence_context_mismatches": evidence_mismatches,
        "artifacts": {
            "paired_case_deltas": "paired_case_deltas.csv",
            "paired_metrics": "paired_metrics.csv",
            "paired_group_deltas": "paired_group_deltas.csv",
            "evidence_strata": "evidence_strata.csv",
            "answerability_decisions": "answerability_decisions.csv",
            "citation_metrics": "citation_metrics.csv",
            "run_reliability": "run_reliability.csv",
            "figures": ["paired_token_f1_delta.svg", "win_tie_loss.svg", "refusal_confusion.svg"],
        },
    }
    write_json(out_dir / "posthoc_analysis.json", summary)
    report = build_report(
        root=root,
        out_dir=out_dir,
        runs=runs,
        pairs=pair_summaries,
        reliability=reliability,
        decisions=decisions,
        citations=citations,
        evidence_mismatches=evidence_mismatches,
        quality_warnings=quality_warnings,
        bootstrap_reps=args.bootstrap_reps,
        seed=args.seed,
    )
    (out_dir / "posthoc_report.md").write_text(report, encoding="utf-8")
    print(f"Analyzed {len(runs)} runs and {len(pair_summaries)} Base/CoT pairs.")
    print(f"Primary paired answerable cases: {len(primary_cases)}")
    print(f"Outputs: {out_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
