from __future__ import annotations

import json
from pathlib import Path

from scripts.run_ablation_batch import run_ablation_batch
from scripts.run_ablation_config import AblationRunOutcome


def _outcome(config_name: str, output_root: Path, *, status: str = "completed") -> AblationRunOutcome:
    run_id = f"run-{config_name}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    return AblationRunOutcome(
        config_name=config_name,
        status=status,
        run_id=run_id,
        output_dir=output_dir,
        artifacts={"manifest": str(output_dir / "manifest.json")},
        counts={"total_input": 1, "successful": 1, "failed": 0, "skipped": 0, "evaluated": 1},
        error="deliberate failure" if status == "failed" else None,
    )


def test_batch_preserves_order_uses_distinct_runs_and_writes_summary(tmp_path: Path) -> None:
    calls: list[str] = []

    def runner(config_name: str, **kwargs):
        calls.append(config_name)
        return _outcome(config_name, kwargs["output_root"])

    result = run_ablation_batch(
        ["first", "second", "third"],
        output_root=tmp_path,
        batch_id="batch-order",
        runner=runner,
    )

    assert calls == ["first", "second", "third"]
    assert [entry.config_name for entry in result.entries] == calls
    assert len({entry.run_id for entry in result.entries}) == 3
    assert result.status == "completed"
    payload = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert payload["requested_config_order"] == calls
    assert [entry["status"] for entry in payload["entries"]] == ["completed", "completed", "completed"]
    assert result.report_path.is_file()


def test_batch_continues_after_exception_and_failed_outcome(tmp_path: Path) -> None:
    calls: list[str] = []

    def runner(config_name: str, **kwargs):
        calls.append(config_name)
        if config_name == "raises":
            raise ValueError("invalid config")
        return _outcome(config_name, kwargs["output_root"], status="failed" if config_name == "fails" else "completed")

    result = run_ablation_batch(
        ["ok-1", "raises", "fails", "ok-2"],
        output_root=tmp_path,
        batch_id="batch-partial",
        runner=runner,
    )

    assert calls == ["ok-1", "raises", "fails", "ok-2"]
    assert [entry.status for entry in result.entries] == ["completed", "failed", "failed", "completed"]
    assert result.entries[1].error == "invalid config"
    assert result.entries[2].retry_recommendation
    assert result.status == "failed"
    assert result.summary_path.is_file()


def test_resume_skips_completed_and_reruns_failed(tmp_path: Path) -> None:
    prior = tmp_path / "prior.json"
    prior.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "config_name": "done",
                        "status": "completed",
                        "run_id": "old-run",
                        "output_directory": "old-output",
                        "artifacts": {"manifest": "old-output/manifest.json"},
                    },
                    {"config_name": "retry", "status": "failed", "run_id": "failed-run"},
                ]
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def runner(config_name: str, **kwargs):
        calls.append(config_name)
        return _outcome(config_name, kwargs["output_root"])

    result = run_ablation_batch(
        ["done", "retry"],
        output_root=tmp_path,
        batch_id="batch-resume",
        resume_summary=prior,
        runner=runner,
    )

    assert calls == ["retry"]
    assert [entry.status for entry in result.entries] == ["skipped", "completed"]
    assert result.entries[0].run_id == "old-run"
    assert result.status == "completed"
