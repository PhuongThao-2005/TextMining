from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from generation.prompt_strategy import (
    PROMPT_TEMPLATE_VERSION,
    PromptStrategy,
    build_generation_prompt,
    prompt_template_hash,
)
from generation.reasoning_client import RawGenerationResponse, parse_generation_response
from retrieval.schema import RetrievalResult
from scripts.aggregate_ablation_results import aggregate_ablation_results
from scripts.run_ablation_batch import _normalize_config_names
from scripts.run_ablation_config import (
    DEFAULT_CONFIG_FILE,
    LLM_ABLATION_CONFIG_NAMES,
    AblationConfigError,
    _build_generator,
    load_ablation_configs,
    run_ablation_config,
    validate_ablation_config,
    validate_llm_ablation_fairness,
)


class _Chunk:
    chunk_id = "chunk-1"
    chunk_text = "Điều 1 quy định nội dung kiểm thử."
    citation_anchor = "Điều 1"
    citation_label = "Điều 1"
    title = "Luật kiểm thử"
    parent_unit_id = "provision-1"
    id_str = "document-1"
    rerank_score = 1.0


class _Retriever:
    def retrieve(self, question: str, *, filter_profile: str, top_n: int) -> RetrievalResult:
        del question, filter_profile, top_n
        return RetrievalResult(chunks=[_Chunk()], total_candidates=1, filter_profile_used="broad")


def test_required_configs_exist_validate_and_have_controlled_differences() -> None:
    configs = load_ablation_configs(DEFAULT_CONFIG_FILE)
    assert all(name in configs for name in LLM_ABLATION_CONFIG_NAMES)
    for name in LLM_ABLATION_CONFIG_NAMES:
        validate_ablation_config(configs[name], config_name=name)

    base = configs["LLM-BaseReasoning"]
    cot = configs["LLM-CoTReasoning"]
    larger = configs["LLM-LargerModel"]
    larger_cot = configs["LLM-LargerModel-CoTReasoning"]
    cot_normalized = copy.deepcopy(cot)
    cot_normalized["generation"]["prompt_strategy"] = base["generation"]["prompt_strategy"]
    larger_normalized = copy.deepcopy(larger)
    larger_normalized["generation"]["model"] = base["generation"]["model"]
    larger_cot_normalized = copy.deepcopy(larger_cot)
    larger_cot_normalized["generation"]["model"] = base["generation"]["model"]
    larger_cot_normalized["generation"]["prompt_strategy"] = base["generation"]["prompt_strategy"]
    assert cot_normalized == base
    assert larger_normalized == base
    assert larger_cot_normalized == base
    assert cot["generation"]["prompt_strategy"] == "reasoning"
    assert larger["generation"]["model"] == "env:LLM_LARGER_MODEL"
    assert larger_cot["generation"]["model"] == "env:LLM_LARGER_MODEL"
    assert larger_cot["generation"]["prompt_strategy"] == "reasoning"


def test_fairness_validator_rejects_unintended_change() -> None:
    configs = load_ablation_configs(DEFAULT_CONFIG_FILE)
    changed = copy.deepcopy(configs)
    changed["LLM-CoTReasoning"]["retrieval"]["top_k"] = 10
    with pytest.raises(AblationConfigError, match="retrieval.top_k"):
        validate_llm_ablation_fairness(changed)


def test_prompt_strategies_are_safe_deterministic_and_share_contract() -> None:
    kwargs = {
        "question": "Quy định nào áp dụng?",
        "answer_type": "extractive",
        "context": "[1] Điều 1\nNội dung.",
    }
    base = build_generation_prompt(**kwargs, strategy=PromptStrategy.BASE)
    cot = build_generation_prompt(**kwargs, strategy=PromptStrategy.REASONING)
    assert base == build_generation_prompt(**kwargs, strategy="base")
    assert "reason internally" not in base.lower()
    assert "step by step" not in base.lower()
    assert "reason internally" in cot.lower()
    assert "return only the final" in base.lower()
    assert "return only the final" in cot.lower()
    for shared in (kwargs["context"], "Có", "Không", "Giải thích:", "Cite supporting context"):
        assert shared in base
        assert shared in cot
    assert prompt_template_hash("base") == prompt_template_hash("base")
    assert prompt_template_hash("base") != prompt_template_hash("reasoning")
    with pytest.raises(ValueError, match="Unknown prompt strategy"):
        build_generation_prompt(**kwargs, strategy="unknown")


def test_reasoning_fields_and_tags_never_enter_final_answer() -> None:
    dedicated = parse_generation_response(
        RawGenerationResponse(
            content="<think>secondary hidden text</think>Final grounded answer",
            reasoning_field="provider hidden reasoning",
        )
    )
    assert dedicated.answer == "Final grounded answer"
    assert "hidden" not in dedicated.answer

    malformed = parse_generation_response(
        RawGenerationResponse(
            content="<think>secret internal analysis\nFinal answer: Preserved answer",
            reasoning_field=None,
        )
    )
    assert malformed.answer == "Preserved answer"
    assert "secret internal analysis" not in malformed.answer

    unmatched_close = parse_generation_response(
        RawGenerationResponse(
            content="secret internal analysis</think>Preserved answer",
            reasoning_field=None,
        )
    )
    assert unmatched_close.answer == "Preserved answer"


@pytest.mark.parametrize(
    ("config_name", "model", "reasoning_expected"),
    [
        ("LLM-BaseReasoning", "base-model", False),
        ("LLM-CoTReasoning", "base-model", True),
        ("LLM-LargerModel", "larger-model", False),
        ("LLM-LargerModel-CoTReasoning", "larger-model", True),
    ],
)
def test_named_configs_construct_expected_generator(
    monkeypatch: pytest.MonkeyPatch,
    config_name: str,
    model: str,
    reasoning_expected: bool,
) -> None:
    configs = load_ablation_configs(DEFAULT_CONFIG_FILE)
    config = copy.deepcopy(configs[config_name]["generation"])
    config["model"] = model
    monkeypatch.setenv("LLM_API_KEY", "sk-test-secret")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    captured: dict[str, Any] = {}

    class _Client:
        def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
            captured.update(base_url=base_url, api_key=api_key, model=model)

        def generate(self, prompt: str, **kwargs: Any) -> RawGenerationResponse:
            captured.update(prompt=prompt, controls=kwargs)
            return RawGenerationResponse(
                content="<think>do not persist</think>Safe final answer",
                reasoning_field=None,
            )

    monkeypatch.setattr("scripts.run_ablation_config.GeneratorClient", _Client)
    generator, secrets = _build_generator(config)
    answer = generator(
        {"qa_id": "qa-1", "question": "Question", "answer_type": "extractive"},
        "unused context",
        [_Chunk()],
    )
    assert answer == "Safe final answer"
    assert captured["model"] == model
    assert ("reason internally" in captured["prompt"].lower()) is reasoning_expected
    assert "sk-test-secret" not in captured["prompt"]
    assert secrets == ["sk-test-secret"]
    assert captured["controls"] == {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 1024,
        "timeout_seconds": 60.0,
        "max_retries": 2,
    }


def test_missing_api_key_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    config = copy.deepcopy(
        load_ablation_configs(DEFAULT_CONFIG_FILE)["LLM-BaseReasoning"]["generation"]
    )
    config["model"] = "fixture-model"
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(AblationConfigError, match="LLM_API_KEY"):
        _build_generator(config)


def _write_runner_config(
    path: Path,
    benchmark: Path,
    corpus: Path,
    output_root: Path,
) -> None:
    path.write_text(
        f"""
schema_version: 1
configs:
  fixture-llm:
    benchmark: {{path: {benchmark.as_posix()}, version: fixture-benchmark-v1}}
    corpus: {{path: {corpus.as_posix()}, version: fixture-corpus-v1}}
    retrieval:
      top_k: 5
      filter_profile: broad
      dense: {{enabled: true, backend: hashing, model: fixture-embedding}}
      sparse: {{enabled: false}}
      graph: {{enabled: false}}
      fusion: {{enabled: false}}
      reranker: {{enabled: false}}
    generation:
      provider: openai_compatible
      model: fixture-model
      prompt_strategy: reasoning
      prompt_template_version: {PROMPT_TEMPLATE_VERSION}
      temperature: 0.0
      top_p: 1.0
      max_output_tokens: 128
      timeout_seconds: 5.0
      max_retries: 1
      api_key_env: LLM_API_KEY
      base_url_env: LLM_BASE_URL
    judge: {{provider: none}}
    agent: {{enabled: false, type: plain_rag}}
    output: {{root: {output_root.as_posix()}}}
    seed: 42
""",
        encoding="utf-8",
    )


def test_runner_persists_safe_metadata_and_isolates_case_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark = tmp_path / "qa.jsonl"
    corpus = tmp_path / "corpus.jsonl"
    config_file = tmp_path / "configs.yaml"
    output_root = tmp_path / "runs"
    cases = [
        {"qa_id": "fail", "question": "Fail?", "reference_answer": "x"},
        {"qa_id": "safe", "question": "Safe?", "reference_answer": "Safe answer"},
    ]
    benchmark.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    corpus.write_text("{}\n", encoding="utf-8")
    _write_runner_config(config_file, benchmark, corpus, output_root)
    monkeypatch.setenv("LLM_API_KEY", "sk-production-secret")

    def generator(qa: dict[str, Any], context: str, chunks: list[Any]) -> str:
        del context, chunks
        if qa["qa_id"] == "fail":
            raise RuntimeError("fixture generation failure")
        parsed = parse_generation_response(
            RawGenerationResponse(
                content="<think>private chain of thought</think>Safe answer",
                reasoning_field=None,
            )
        )
        return parsed.answer

    outcome = run_ablation_config(
        "fixture-llm",
        config_file=config_file,
        output_root=output_root,
        run_id="fixture-llm-run",
        retriever=_Retriever(),
        generator=generator,
        project_root=tmp_path,
    )
    assert outcome.status == "completed"
    assert outcome.counts["successful"] == 1
    assert outcome.counts["failed"] == 1
    manifest_text = (outcome.output_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    assert manifest["generation_provider"] == "openai_compatible"
    assert manifest["generation_model"] == "fixture-model"
    assert manifest["prompt_strategy"] == "reasoning"
    assert manifest["prompt_template_version"] == PROMPT_TEMPLATE_VERSION
    assert manifest["prompt_template_hash"] == prompt_template_hash("reasoning")
    assert manifest["generation_decoding"]["max_retries"] == 1
    assert "sk-production-secret" not in manifest_text
    predictions = (outcome.output_dir / "e2e_predictions.jsonl").read_text(encoding="utf-8")
    assert "Safe answer" in predictions
    assert "private chain of thought" not in predictions

    monkeypatch.delenv("LLM_API_KEY")
    missing_key = run_ablation_config(
        "fixture-llm",
        config_file=config_file,
        output_root=output_root,
        run_id="missing-api-key",
        retriever=_Retriever(),
        project_root=tmp_path,
    )
    assert missing_key.status == "failed"
    assert missing_key.error is not None
    assert "LLM_API_KEY" in missing_key.error


def _write_aggregate_llm_run(
    root: Path,
    run_id: str,
    config_name: str,
    *,
    model: str,
    strategy: str,
) -> None:
    run_dir = root / run_id
    run_dir.mkdir()
    generation = {
        "provider": "openai_compatible",
        "model": model,
        "prompt_strategy": strategy,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_output_tokens": 1024,
        "timeout_seconds": 60.0,
        "max_retries": 2,
    }
    manifest = {
        "run_id": run_id,
        "config_name": config_name,
        "resolved_config": {
            "benchmark": {"path": "data/benchmark/qa_final.jsonl", "version": "bench-v1"},
            "corpus": {"path": "data/v2/documents.jsonl", "version": "corpus-v1"},
            "generation": generation,
        },
        "config_hash": f"hash-{run_id}",
        "start_time": "2026-07-31T00:00:00+00:00",
        "end_time": "2026-07-31T00:01:00+00:00",
        "status": "completed",
        "benchmark_path": "data/benchmark/qa_final.jsonl",
        "benchmark_version": "bench-v1",
        "corpus_path": "data/v2/documents.jsonl",
        "corpus_version": "corpus-v1",
        "output_directory": str(run_dir),
        "output_artifacts": {},
        "completed_case_count": 1,
        "failed_case_count": 0,
        "skipped_case_count": 0,
        "evaluated_case_count": 1,
        "generation_provider": generation["provider"],
        "generation_model": model,
        "prompt_strategy": strategy,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_template_hash": prompt_template_hash(strategy),
        "generation_decoding": {
            key: generation[key]
            for key in (
                "temperature",
                "top_p",
                "max_output_tokens",
                "timeout_seconds",
                "max_retries",
            )
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "resolved_config.yaml").write_text("fixture: true\n", encoding="utf-8")
    (run_dir / "e2e_metrics.json").write_text(
        json.dumps({"overall": {"token_f1": 0.5}}), encoding="utf-8"
    )
    (run_dir / "latency.json").write_text(
        json.dumps({"stages": {"total": {"mean": 10.0}}}), encoding="utf-8"
    )
    (run_dir / "e2e_predictions.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "errors.jsonl").write_text("", encoding="utf-8")
    (run_dir / "report.md").write_text("# Fixture\n", encoding="utf-8")


def test_aggregator_compares_intended_prompt_and_model_variants(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_aggregate_llm_run(
        runs, "base", "LLM-BaseReasoning", model="base-model", strategy="base"
    )
    _write_aggregate_llm_run(
        runs, "cot", "LLM-CoTReasoning", model="base-model", strategy="reasoning"
    )
    _write_aggregate_llm_run(
        runs, "larger", "LLM-LargerModel", model="larger-model", strategy="base"
    )
    _write_aggregate_llm_run(
        runs,
        "larger-cot",
        "LLM-LargerModel-CoTReasoning",
        model="larger-model",
        strategy="reasoning",
    )
    result = aggregate_ablation_results(runs)
    assert result.comparable_count == 4
    with result.output_csv.open(encoding="utf-8", newline="") as handle:
        rows = {row["config_name"]: row for row in csv.DictReader(handle)}
    assert rows["LLM-CoTReasoning"]["prompt_strategy"] == "reasoning"
    assert rows["LLM-LargerModel"]["generation_model"] == "larger-model"
    assert rows["LLM-LargerModel-CoTReasoning"]["prompt_strategy"] == "reasoning"
    assert rows["LLM-BaseReasoning"]["max_retries"] == "2"


def test_batch_cli_name_normalization_preserves_requested_order() -> None:
    assert _normalize_config_names([",".join(LLM_ABLATION_CONFIG_NAMES)]) == list(
        LLM_ABLATION_CONFIG_NAMES
    )
