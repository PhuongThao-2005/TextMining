import json
from pathlib import Path
from typing import Any

import pytest

from service.ui_runtime import discover_artifact_candidates, scan_production_readiness


def config(tmp_path: Path, *, provider: str = "reference") -> dict[str, Any]:
    benchmark = tmp_path / "qa.jsonl"
    corpus = tmp_path / "corpus.jsonl"
    benchmark.write_text("{}\n", encoding="utf-8")
    corpus.write_text("{}\n", encoding="utf-8")
    generation: dict[str, Any] = {
        "provider": provider, "model": "reference" if provider == "reference" else "fixture-model",
        "prompt_strategy": "base", "temperature": 0.0, "top_p": 1.0,
        "max_output_tokens": 100, "timeout_seconds": 5.0, "max_retries": 0,
    }
    if provider == "openai_compatible":
        generation.update({"api_key_env": "TEST_KEY", "base_url_env": "TEST_URL"})
    return {
        "benchmark": {"path": str(benchmark), "version": "fixture-v1"},
        "corpus": {"path": str(corpus), "version": "fixture-v1"},
        "retrieval": {
            "top_k": 5, "filter_profile": "broad",
            "dense": {"enabled": True, "backend": "faiss", "model": "fixture-model", "dimension": 8,
                      "index_path": "index", "index_version": "fixture-index-v1"},
            "sparse": {"enabled": False}, "graph": {"enabled": False},
            "fusion": {"enabled": False}, "reranker": {"enabled": False},
        },
        "generation": generation, "judge": {"provider": "none"},
        "agent": {"enabled": False, "mode": "none", "implementation_status": "implemented"},
        "output": {"root": str(tmp_path / "runs")}, "seed": 42,
    }


def write_artifact(root: Path, *, name: str = "index", **overrides: Any) -> Path:
    index = root / name
    index.mkdir(parents=True)
    (index / "index.faiss").write_bytes(b"fixture")
    (index / "payloads.jsonl").write_text("{}\n{}\n", encoding="utf-8")
    manifest = {
        "index_path": str(index), "embedding_model": "fixture-model",
        "embedding_dimension": 8, "corpus_version": "fixture-v1",
        "index_version": "fixture-index-v1", "payload_count": 2,
        "vector_count": 2, "config_name": "fixture", "created_at": "2026-08-02T00:00:00Z",
    }
    manifest.update(overrides)
    (index / "index_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return index


def scan(tmp_path: Path, value: dict[str, Any], **kwargs: Any):
    return scan_production_readiness(
        {"fixture": value}, "fixture", project_root=tmp_path,
        environ=kwargs.pop("environ", {}), package_available=kwargs.pop("package_available", lambda _: True),
        search_roots=kwargs.pop("search_roots", (Path("index"), Path("artifacts"))), **kwargs,
    )


def test_missing_config_and_required_files_are_blockers(tmp_path: Path) -> None:
    missing = scan_production_readiness({}, "missing", project_root=tmp_path)
    assert not missing.ready and "Unknown" in missing.blockers[0]
    result = scan(tmp_path, config(tmp_path))
    text = " ".join(result.blockers)
    assert not result.ready and "index.faiss" in text and "payloads.jsonl" in text


def test_missing_manifest_is_a_blocker(tmp_path: Path) -> None:
    index = tmp_path / "index"
    index.mkdir()
    (index / "index.faiss").write_bytes(b"fixture")
    (index / "payloads.jsonl").write_text("{}\n", encoding="utf-8")
    result = scan(tmp_path, config(tmp_path))
    assert not result.ready and any("manifest" in value.lower() for value in result.blockers)


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"embedding_model": "other"}, "Embedding identity mismatch"),
        ({"embedding_dimension": 99}, "Embedding dimension mismatch"),
        ({"corpus_version": "other"}, "Corpus identity mismatch"),
        ({"payload_count": 99}, "Payload count mismatch"),
    ],
)
def test_manifest_compatibility_mismatches_block(tmp_path: Path, override: dict[str, Any], expected: str) -> None:
    write_artifact(tmp_path, **override)
    result = scan(tmp_path, config(tmp_path))
    assert not result.ready and expected in " ".join(result.blockers)


def test_missing_dependency_and_provider_environment_are_blockers_without_secrets(tmp_path: Path) -> None:
    write_artifact(tmp_path)
    value = config(tmp_path, provider="openai_compatible")
    result = scan(tmp_path, value, package_available=lambda name: name != "faiss", environ={})
    text = json.dumps({"checks": [vars(item) for item in result.checks], "blockers": result.blockers})
    assert "faiss-cpu" in text and "TEST_KEY" in text and "TEST_URL" in text
    assert "secret-value" not in text


def test_valid_manifest_and_runtime_are_ready(tmp_path: Path) -> None:
    index = write_artifact(tmp_path)
    result = scan(tmp_path, config(tmp_path))
    assert result.ready and result.selected_artifact is not None
    assert result.selected_artifact.index_dir == index
    assert result.embedding_identity == "fixture-model"


def test_discovery_is_deterministic_and_multiple_candidates_require_selection(tmp_path: Path) -> None:
    value = config(tmp_path)
    value["retrieval"]["dense"]["index_path"] = "missing-index"
    first = write_artifact(tmp_path / "artifacts", name="a")
    second = write_artifact(tmp_path / "artifacts", name="b")
    candidates = discover_artifact_candidates(tmp_path, search_roots=(Path("artifacts"),))
    assert [item.index_dir.name for item in candidates] == ["a", "b"]
    ambiguous = scan(tmp_path, value, search_roots=(Path("artifacts"),))
    assert not ambiguous.ready and "choose one" in " ".join(ambiguous.blockers).lower()
    selected = scan(tmp_path, value, search_roots=(Path("artifacts"),), selected_artifact=second)
    assert selected.ready and selected.selected_artifact and selected.selected_artifact.index_dir == second
    assert first != second
