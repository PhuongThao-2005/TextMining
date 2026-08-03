from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from retrieval.schema import RetrievalResult
import scripts.run_ablation_config as runner_module
from scripts.run_ablation_config import (
    AblationConfigError,
    DEFAULT_CONFIG_FILE,
    build_ablation_stack,
    create_run_id,
    load_ablation_configs,
    resolve_ablation_config,
    run_ablation_config,
    validate_ablation_config,
)


class _Chunk:
    chunk_id = "c1"
    chunk_text = "Căn cứ pháp lý"
    citation_anchor = "Điều 1"
    citation_label = ""
    parent_unit_id = "p1"
    id_str = "d1"
    rerank_score = 1.0


class _Retriever:
    def retrieve(self, question: str, *, filter_profile: str, top_n: int) -> RetrievalResult:
        del question, filter_profile, top_n
        return RetrievalResult(chunks=[_Chunk()], total_candidates=1, filter_profile_used="broad")


def _config_payload(benchmark: Path, corpus: Path, output_root: Path) -> str:
    return f"""
schema_version: 1
configs:
  baseline:
    benchmark:
      path: {benchmark.as_posix()}
      version: fixture-v1
    corpus:
      path: {corpus.as_posix()}
      version: fixture-v1
    retrieval:
      top_k: 5
      filter_profile: broad
      dense:
        enabled: true
        backend: hashing
      sparse:
        enabled: false
      graph:
        enabled: false
      fusion:
        enabled: false
      reranker:
        enabled: false
    generation:
      provider: reference
      model: reference
    judge:
      provider: none
    agent:
      enabled: false
    output:
      root: {output_root.as_posix()}
    seed: 42
"""


def _fixture_files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    benchmark = tmp_path / "qa.jsonl"
    corpus = tmp_path / "corpus.jsonl"
    output_root = tmp_path / "runs"
    config_file = tmp_path / "configs.yaml"
    benchmark.write_text(
        json.dumps(
            {
                "qa_id": "qa-1",
                "question": "Câu hỏi",
                "reference_answer": "Đáp án",
                "answer_type": "extractive",
                "category": "contract",
                "difficulty": "easy",
                "ground_truth": {"chunk_ids": ["c1"]},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    corpus.write_text("{}\n", encoding="utf-8")
    config_file.write_text(_config_payload(benchmark, corpus, output_root), encoding="utf-8")
    return benchmark, corpus, output_root, config_file


def test_load_resolve_and_validate_exact_config(tmp_path: Path) -> None:
    _, _, _, config_file = _fixture_files(tmp_path)
    configs = load_ablation_configs(config_file)

    resolved = resolve_ablation_config(configs, "baseline")
    validate_ablation_config(resolved, config_name="baseline")

    assert list(configs) == ["baseline"]
    with pytest.raises(AblationConfigError, match="Unknown ablation config"):
        resolve_ablation_config(configs, "BASELINE")


def test_duplicate_yaml_key_is_rejected(tmp_path: Path) -> None:
    config_file = tmp_path / "duplicate.yaml"
    config_file.write_text("schema_version: 1\nconfigs:\n  duplicate: {}\n  duplicate: {}\n", encoding="utf-8")

    with pytest.raises(AblationConfigError, match="Duplicate YAML key"):
        load_ablation_configs(config_file)


def test_incomplete_and_invalid_backend_are_rejected(tmp_path: Path) -> None:
    _, _, _, config_file = _fixture_files(tmp_path)
    config = resolve_ablation_config(load_ablation_configs(config_file), "baseline")
    del config["benchmark"]["path"]
    with pytest.raises(AblationConfigError, match="benchmark.path"):
        validate_ablation_config(config, config_name="baseline")

    config = resolve_ablation_config(load_ablation_configs(config_file), "baseline")
    config["retrieval"]["dense"]["backend"] = "unknown"
    with pytest.raises(AblationConfigError, match="Unsupported dense backend"):
        validate_ablation_config(config, config_name="baseline")


def test_missing_required_path_is_rejected_before_run_directory(tmp_path: Path) -> None:
    benchmark, _, output_root, config_file = _fixture_files(tmp_path)
    benchmark.unlink()

    with pytest.raises(AblationConfigError, match="benchmark.path"):
        run_ablation_config(
            "baseline",
            config_file=config_file,
            output_root=output_root,
            retriever=_Retriever(),
            generator=lambda qa, context, chunks: str(qa["reference_answer"]),
            project_root=tmp_path,
        )

    assert not output_root.exists()


def test_run_creates_manifest_and_complete_artifact_set(tmp_path: Path) -> None:
    _, _, output_root, config_file = _fixture_files(tmp_path)

    outcome = run_ablation_config(
        "baseline",
        config_file=config_file,
        output_root=output_root,
        run_id="fixture-run",
        retriever=_Retriever(),
        generator=lambda qa, context, chunks: str(qa["reference_answer"]),
        project_root=tmp_path,
    )

    assert outcome.status == "completed"
    assert outcome.run_id == "fixture-run"
    assert outcome.counts["successful"] == 1
    expected = {
        "manifest.json",
        "resolved_config.yaml",
        "e2e_predictions.jsonl",
        "e2e_metrics.json",
        "latency.json",
        "errors.jsonl",
        "report.md",
    }
    assert {path.name for path in outcome.output_dir.iterdir()} == expected
    manifest = json.loads((outcome.output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["completed_case_count"] == 1
    assert manifest["config_name"] == "baseline"
    assert manifest["config_hash"]


def test_existing_run_directory_is_never_overwritten(tmp_path: Path) -> None:
    _, _, output_root, config_file = _fixture_files(tmp_path)
    kwargs: dict[str, Any] = {
        "config_file": config_file,
        "output_root": output_root,
        "run_id": "collision",
        "retriever": _Retriever(),
        "generator": lambda qa, context, chunks: str(qa["reference_answer"]),
        "project_root": tmp_path,
    }
    run_ablation_config("baseline", **kwargs)

    with pytest.raises(AblationConfigError, match="refusing to overwrite"):
        run_ablation_config("baseline", **kwargs)


def test_run_id_is_sanitized_and_deterministic_for_supplied_time() -> None:
    now = datetime(2026, 7, 28, 1, 2, 3, 456789, tzinfo=timezone.utc)

    run_id = create_run_id("LLM Base/Reasoning", config_hash="abcdef123456", now=now)

    assert run_id == "20260728T010203456789Z_llm-base-reasoning_abcdef12"


def test_official_llm_config_builds_full_stack_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    config = resolve_ablation_config(load_ablation_configs(DEFAULT_CONFIG_FILE), "LLM-BaseReasoning")
    dense = object()
    sparse = object()
    hybrid = object()
    graph = object()
    expansion = object()
    full_stack = object()
    captured: dict[str, Any] = {}

    monkeypatch.setattr(runner_module, "build_vector_retriever", lambda runtime: dense)
    monkeypatch.setattr(runner_module.BM25SparseRetriever, "load", lambda path: sparse)

    def build_hybrid(**kwargs):
        captured["hybrid"] = kwargs
        return hybrid

    monkeypatch.setattr(runner_module, "HybridRetriever", build_hybrid)
    monkeypatch.setattr(runner_module, "load_knowledge_graph", lambda path: type("Loaded", (), {"graph": graph})())
    monkeypatch.setattr(runner_module, "GraphExpansion", lambda value: expansion if value is graph else None)

    def build_full_stack(**kwargs):
        captured["full_stack"] = kwargs
        return full_stack

    monkeypatch.setattr(runner_module, "FullStackRetriever", build_full_stack)
    monkeypatch.setattr(runner_module, "_build_generator", lambda value: (lambda *_: "answer", []))
    monkeypatch.setattr(runner_module, "_build_judge", lambda value: (None, []))

    retriever, _, _, _ = build_ablation_stack(config)
    assert retriever is full_stack
    assert captured["hybrid"]["dense_retriever"] is dense
    assert captured["hybrid"]["sparse_retriever"] is sparse
    assert captured["hybrid"]["use_rrf"] is True
    assert captured["hybrid"]["use_cross_encoder"] is True
    assert captured["full_stack"]["base_retriever"] is hybrid
    assert captured["full_stack"]["dense_retriever"] is dense
    assert captured["full_stack"]["graph_expansion"] is expansion
