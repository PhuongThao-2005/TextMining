#!/usr/bin/env python3
"""Run an ordered batch of named ablation configurations."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.io_utils import write_json  # noqa: E402
from scripts.run_ablation_config import (  # noqa: E402
    DEFAULT_CONFIG_FILE,
    DEFAULT_OUTPUT_ROOT,
    AblationConfigError,
    AblationRunOutcome,
    run_ablation_config,
)


@dataclass(frozen=True)
class BatchEntry:
    config_name: str
    status: str
    run_id: str | None
    output_directory: str | None
    error: str | None
    retry_recommendation: str | None
    artifacts: dict[str, str]


@dataclass(frozen=True)
class BatchOutcome:
    batch_id: str
    status: str
    output_dir: Path
    entries: list[BatchEntry]
    summary_path: Path
    report_path: Path


RunnerFunction = Callable[..., AblationRunOutcome]


def run_ablation_batch(
    config_names: Sequence[str],
    *,
    config_file: Path = DEFAULT_CONFIG_FILE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    batch_id: str | None = None,
    limit: int | None = None,
    resume_summary: Path | None = None,
    runner: RunnerFunction = run_ablation_config,
) -> BatchOutcome:
    if not config_names:
        raise AblationConfigError("At least one config name is required.")
    requested = list(config_names)
    selected_batch_id = batch_id or create_batch_id(requested)
    batch_dir = output_root / "batches" / selected_batch_id
    try:
        batch_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise AblationConfigError(f"Batch directory already exists; refusing to overwrite: {batch_dir}") from exc

    prior_completed = _load_prior_completed(resume_summary)
    started = datetime.now(timezone.utc)
    entries: list[BatchEntry] = []
    for config_name in requested:
        prior = prior_completed.get(config_name)
        if prior is not None:
            entries.append(
                BatchEntry(
                    config_name=config_name,
                    status="skipped",
                    run_id=prior.get("run_id"),
                    output_directory=prior.get("output_directory"),
                    error=None,
                    retry_recommendation=None,
                    artifacts=dict(prior.get("artifacts") or {}),
                )
            )
            continue
        try:
            outcome = runner(
                config_name,
                config_file=config_file,
                output_root=output_root,
                limit=limit,
                command_args=["--batch-id", selected_batch_id],
            )
            entries.append(
                BatchEntry(
                    config_name=config_name,
                    status=outcome.status,
                    run_id=outcome.run_id,
                    output_directory=str(outcome.output_dir) if outcome.output_dir else None,
                    error=outcome.error,
                    retry_recommendation=_retry_recommendation(outcome.status),
                    artifacts=outcome.artifacts,
                )
            )
        except Exception as exc:
            entries.append(
                BatchEntry(
                    config_name=config_name,
                    status="failed",
                    run_id=None,
                    output_directory=None,
                    error=str(exc),
                    retry_recommendation="Fix configuration/runtime error, then rerun or resume this batch.",
                    artifacts={},
                )
            )

    status = "completed" if all(entry.status in {"completed", "skipped"} for entry in entries) else "failed"
    ended = datetime.now(timezone.utc)
    summary = {
        "batch_id": selected_batch_id,
        "status": status,
        "requested_config_order": requested,
        "start_time": started.isoformat(),
        "end_time": ended.isoformat(),
        "resume_source": str(resume_summary) if resume_summary else None,
        "entries": [asdict(entry) for entry in entries],
    }
    summary_path = batch_dir / "batch_summary.json"
    report_path = batch_dir / "batch_report.md"
    write_json(summary_path, summary)
    _write_batch_report(report_path, summary)
    return BatchOutcome(
        batch_id=selected_batch_id,
        status=status,
        output_dir=batch_dir,
        entries=entries,
        summary_path=summary_path,
        report_path=report_path,
    )


def create_batch_id(config_names: Sequence[str], *, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S%fZ")
    digest = hashlib.sha256("\0".join(config_names).encode("utf-8")).hexdigest()[:8]
    return f"{timestamp}_batch_{digest}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an ordered batch of ablation configs.")
    parser.add_argument("--configs", nargs="+", required=True)
    parser.add_argument("--config-file", type=Path, default=DEFAULT_CONFIG_FILE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        metavar="BATCH_SUMMARY",
        help="Skip configs completed in a prior batch_summary.json; failed/needs-rerun configs run again.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_names = _normalize_config_names(args.configs)
    try:
        outcome = run_ablation_batch(
            config_names,
            config_file=args.config_file,
            output_root=args.output_root,
            batch_id=args.batch_id,
            limit=args.limit,
            resume_summary=args.resume,
        )
    except AblationConfigError as exc:
        print(f"Batch configuration error: {exc}", file=sys.stderr)
        return 2
    print(f"Batch ID: {outcome.batch_id}")
    for entry in outcome.entries:
        suffix = f" ({entry.error})" if entry.error else ""
        print(f"- {entry.config_name}: {entry.status}{suffix}")
    print(f"Summary: {outcome.summary_path}")
    print(f"Report: {outcome.report_path}")
    return 0 if outcome.status == "completed" else 1


def _normalize_config_names(values: Sequence[str]) -> list[str]:
    names: list[str] = []
    for value in values:
        names.extend(part.strip() for part in value.split(",") if part.strip())
    if not names:
        raise AblationConfigError("At least one non-empty config name is required.")
    return names


def _load_prior_completed(summary_path: Path | None) -> dict[str, dict[str, Any]]:
    if summary_path is None:
        return {}
    if not summary_path.is_file():
        raise AblationConfigError(f"Resume summary not found: {summary_path}")
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AblationConfigError(f"Resume summary is not valid JSON: {summary_path}") from exc
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise AblationConfigError("Resume summary must contain an 'entries' list.")
    completed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("status") == "completed" and isinstance(entry.get("config_name"), str):
            completed[entry["config_name"]] = entry
    return completed


def _retry_recommendation(status: str) -> str | None:
    if status in {"failed", "needs-rerun"}:
        return "Inspect the run manifest/errors.jsonl, fix the cause, then rerun or resume."
    if status == "deferred":
        return "Enable the requested stack component or retain the documented defer reason."
    return None


def _write_batch_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Ablation Batch Report",
        "",
        f"- Batch ID: `{summary['batch_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Started: {summary['start_time']}",
        f"- Ended: {summary['end_time']}",
        "",
        "| Order | Config | Status | Run ID | Error |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for index, entry in enumerate(summary["entries"], start=1):
        error = str(entry.get("error") or "").replace("|", "\\|")
        lines.append(
            f"| {index} | {entry['config_name']} | {entry['status']} | "
            f"{entry.get('run_id') or '—'} | {error or '—'} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
