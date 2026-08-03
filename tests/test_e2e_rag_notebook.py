from __future__ import annotations

import ast
import builtins
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import nbformat
import pytest

from evaluation.artifacts import ArtifactLoadError, load_run_artifacts, validate_run_parameters
from evaluation.export import export_run_artifacts
from scripts.run_ablation_config import apply_runtime_path_overrides


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "e2e_rag_eval.ipynb"


def _notebook() -> Any:
    return nbformat.read(NOTEBOOK_PATH, as_version=4)


def _source() -> str:
    return "\n".join(cell.source for cell in _notebook().cells)


def _cell_containing(fragment: str) -> str:
    return next(cell.source for cell in _notebook().cells if fragment in cell.source)


def _helper_namespace(fragment: str) -> dict[str, Any]:
    source = _cell_containing(fragment)
    tree = ast.parse(source)
    safe_nodes = (
        ast.Import,
        ast.ImportFrom,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    body = [node for node in tree.body if isinstance(node, safe_nodes)]
    body.extend(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and all(isinstance(target, ast.Name) and target.id.isupper() for target in node.targets)
    )
    module = ast.Module(body=body, type_ignores=[])
    namespace: dict[str, Any] = {
        "Path": Path,
        "os": os,
        "re": __import__("re"),
        "shutil": __import__("shutil"),
        "subprocess": subprocess,
        "sys": __import__("sys"),
        "importlib": __import__("importlib"),
        "GITHUB_TOKEN_SECRET_NAME": "GITHUB_TOKEN",
        "KAGGLE_INPUT_ROOT": Path("/kaggle/input"),
        "KAGGLE_WORKING_ROOT": Path("/kaggle/working"),
    }
    exec(compile(module, "<notebook-cell>", "exec"), namespace)
    return namespace


def _valid_checkout(path: Path) -> None:
    (path / ".git").mkdir(parents=True)
    (path / "configs").mkdir()
    (path / "configs" / "ablation_configs.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (path / "scripts").mkdir()
    (path / "scripts" / "run_ablation_config.py").write_text("", encoding="utf-8")
    (path / "src").mkdir()


def _config() -> dict[str, Any]:
    return {
        "benchmark": {"path": "old-benchmark", "version": "v1"},
        "corpus": {"path": "old-corpus", "version": "v1"},
        "retrieval": {
            "top_k": 5,
            "dense": {"enabled": True, "backend": "faiss", "index_path": "old-index"},
            "graph": {"enabled": False},
        },
        "generation": {"provider": "reference", "model": "reference"},
        "agent": {"enabled": False},
        "output": {"root": "old-runs"},
        "metadata": {},
    }


def _completed_run(path: Path, *, secret: str | None = None) -> None:
    path.mkdir()
    manifest = {"run_id": path.name, "status": "completed"}
    if secret:
        manifest["note"] = secret
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (path / "resolved_config.yaml").write_text("config: safe\n", encoding="utf-8")
    (path / "e2e_predictions.jsonl").write_text("{}\n", encoding="utf-8")
    (path / "e2e_metrics.json").write_text("{}\n", encoding="utf-8")
    (path / "latency.json").write_text("{}\n", encoding="utf-8")
    (path / "errors.jsonl").write_text("", encoding="utf-8")
    (path / "report.md").write_text("# Report\n", encoding="utf-8")


def test_repository_has_no_conflict_markers() -> None:
    markers = ("<" * 7, ">" * 7)
    affected = [
        ROOT / "notebooks" / "e2e_rag_eval.ipynb",
        ROOT / "src" / "evaluation" / "artifacts.py",
        ROOT / "scripts" / "run_ablation_config.py",
        ROOT / "docs" / "e2e_rag_eval.md",
    ]
    for path in affected:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert not any(marker in text for marker in markers)


def test_notebook_is_valid_clean_and_secret_safe() -> None:
    notebook = _notebook()
    assert notebook.nbformat == 4
    assert notebook.metadata.kernelspec.name == "python3"
    assert all(cell.get("execution_count") is None for cell in notebook.cells if cell.cell_type == "code")
    assert all(cell.get("outputs") == [] for cell in notebook.cells if cell.cell_type == "code")
    source = _source()
    assert "RUN_MODE = \"inspect\"" in source
    assert "api.github.com" not in source
    assert "https://github.com/" in source
    assert not __import__("re").search(r"[A-Za-z]:\\\\", source)
    assert not __import__("re").search(r"(?i)(api[_-]?key|token)\s*=\s*[\"'][A-Za-z0-9_-]{20,}", source)


def test_notebook_order_is_clone_first() -> None:
    source = _source()
    positions = [
        source.index("REPO_URL ="),
        source.index("def ensure_repository"),
        source.index("os.chdir(REPO_DIR)"),
        source.index("def setup_dependencies"),
        source.index("def load_kaggle_secrets"),
        source.index("def locate_input_file"),
        source.index("def prepare_faiss_runtime_sources"),
        source.index("from scripts.run_ablation_config import"),
        source.index("configs = load_ablation_configs"),
        source.index("service_preflight = run_preflight"),
        source.index("if RUN_MODE == \"inspect\""),
        source.index("export_run_artifacts("),
        source.index("def display_rows"),
    ]
    assert positions == sorted(positions)
    assert source.index("from scripts.run_ablation_config import") > source.index("setup_dependencies(")


def test_clone_missing_repository_without_network(tmp_path: Path) -> None:
    ns = _helper_namespace("def ensure_repository")
    calls: list[list[str]] = []

    def fake_git(args, **kwargs):
        calls.append(list(args))
        if "clone" in args:
            _valid_checkout(Path(args[-1]))
            return ""
        if args[:2] == ["rev-parse", "HEAD"]:
            return "abc123"
        return ""

    ns["_git"] = fake_git
    result = ns["ensure_repository"]("https://github.com/example/repo.git", "main", tmp_path / "repo")
    assert result["git_commit"] == "abc123"
    assert any("clone" in call for call in calls)
    assert ["remote", "set-url", "origin", "https://github.com/example/repo.git"] in calls


def test_reuse_and_update_existing_checkout(tmp_path: Path) -> None:
    ns = _helper_namespace("def ensure_repository")
    checkout = tmp_path / "repo"
    _valid_checkout(checkout)
    calls: list[list[str]] = []

    def fake_git(args, **kwargs):
        calls.append(list(args))
        return "abc123" if args[:2] == ["rev-parse", "HEAD"] else ""

    ns["_git"] = fake_git
    ns["ensure_repository"]("https://github.com/example/repo.git", "main", checkout, pull_if_exists=False)
    assert not any("pull" in call for call in calls)
    calls.clear()
    ns["ensure_repository"]("https://github.com/example/repo.git", "main", checkout, pull_if_exists=True)
    assert any("pull" in call for call in calls)


def test_force_reclone_deletes_only_target(tmp_path: Path) -> None:
    ns = _helper_namespace("def ensure_repository")
    checkout = tmp_path / "repo"
    checkout.mkdir()
    (checkout / "stale").write_text("old", encoding="utf-8")
    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")

    def fake_git(args, **kwargs):
        if "clone" in args:
            _valid_checkout(Path(args[-1]))
        return "abc123" if args[:2] == ["rev-parse", "HEAD"] else ""

    ns["_git"] = fake_git
    ns["ensure_repository"](
        "https://github.com/example/repo.git", "main", checkout, force_reclone=True
    )
    assert sibling.read_text(encoding="utf-8") == "keep"
    assert not (checkout / "stale").exists()


def test_invalid_checkout_and_sanitized_git_errors(tmp_path: Path) -> None:
    ns = _helper_namespace("def ensure_repository")
    invalid = tmp_path / "repo"
    invalid.mkdir()
    with pytest.raises(RuntimeError, match="not a valid checkout"):
        ns["ensure_repository"]("https://github.com/example/repo.git", "main", invalid)
    value = ns["sanitize_git_error"](
        "https://secret@github.com/example/repo token=secret", ("secret",)
    )
    assert "secret" not in value


def test_private_clone_never_persists_authenticated_remote(tmp_path: Path) -> None:
    ns = _helper_namespace("def ensure_repository")
    calls: list[list[str]] = []

    def fake_git(args, **kwargs):
        calls.append(list(args))
        if "clone" in args:
            _valid_checkout(Path(args[-1]))
        return "abc123" if args[:2] == ["rev-parse", "HEAD"] else ""

    ns["_git"] = fake_git
    safe_url = "https://github.com/example/repo.git"
    ns["ensure_repository"](
        safe_url,
        "main",
        tmp_path / "repo",
        private_repository=True,
        token_loader=lambda: "top-secret-token",
    )
    remote_calls = [call for call in calls if call[:3] == ["remote", "set-url", "origin"]]
    assert remote_calls and all(call[-1] == safe_url for call in remote_calls)
    assert all("@" not in call[-1] for call in remote_calls)


def test_secrets_preserve_environment_and_report_only_status() -> None:
    ns = _helper_namespace("def load_kaggle_secrets")
    env = {"LLM_API_KEY": "existing"}
    class Client:
        def get_secret(self, name):
            return {"LLM_BASE_URL": "https://provider.invalid"}.get(name)
    status = ns["load_kaggle_secrets"](
        {"LLM_API_KEY": "LLM_API_KEY", "LLM_BASE_URL": "LLM_BASE_URL", "MISSING": "MISSING"},
        environ=env,
        client_factory=Client,
    )
    assert env["LLM_API_KEY"] == "existing"
    assert env["LLM_BASE_URL"] == "https://provider.invalid"
    assert status == {"LLM_API_KEY": "configured", "LLM_BASE_URL": "configured", "MISSING": "missing"}
    assert "existing" not in json.dumps(status)
    assert "provider.invalid" not in json.dumps(status)


def test_pandas_and_pyarrow_are_optional() -> None:
    source = _source()
    dependency_position = source.index("def setup_dependencies")
    pandas_position = source.index("import pandas as pd")
    assert pandas_position > dependency_position
    assert "pip\", \"install\", \"pandas" not in source
    assert "pip\", \"install\", \"pyarrow" not in source

    artifacts_source = (ROOT / "src" / "evaluation" / "artifacts.py").read_text(encoding="utf-8")
    assert "import pandas" not in artifacts_source
    assert "import pyarrow" not in artifacts_source
    assert "Restart the Kaggle session and rerun from the first cell." in source


def test_artifact_loading_does_not_import_pandas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = tmp_path / "run"
    _completed_run(run)
    original_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.startswith(("pandas", "pyarrow")):
            raise ImportError(name)
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    artifacts = load_run_artifacts(run, require_completed=True)
    assert artifacts.status == "completed"
    assert artifacts.predictions and "citations" not in artifacts.predictions[0]


def test_runtime_path_overrides_are_validated_persisted_and_do_not_mutate_source(tmp_path: Path) -> None:
    paths = {}
    for name in (
        "benchmark.jsonl", "corpus.jsonl", "index.faiss", "payloads.jsonl",
        "manifest.json", "bm25_index.pkl", "bm25_metadata.pkl", "graph.pkl",
    ):
        path = tmp_path / name
        path.write_text("{}", encoding="utf-8")
        paths[name] = path
    source = _config()
    before = json.loads(json.dumps(source))
    resolved = apply_runtime_path_overrides(
        source,
        benchmark_source=paths["benchmark.jsonl"],
        corpus_source=paths["corpus.jsonl"],
        faiss_index_source=paths["index.faiss"],
        faiss_payloads_source=paths["payloads.jsonl"],
        faiss_manifest_source=paths["manifest.json"],
        bm25_index_source=paths["bm25_index.pkl"],
        bm25_metadata_source=paths["bm25_metadata.pkl"],
        graph_source=paths["graph.pkl"],
        runs_root=tmp_path / "runs",
        selected_device="cpu",
    )
    assert source == before
    assert resolved["benchmark"]["path"] == str(paths["benchmark.jsonl"].resolve())
    assert resolved["corpus"]["path"] == str(paths["corpus.jsonl"].resolve())
    assert resolved["retrieval"]["dense"]["index_file"] == str(paths["index.faiss"].resolve())
    assert resolved["retrieval"]["dense"]["payloads_path"] == str(paths["payloads.jsonl"].resolve())
    assert resolved["retrieval"]["dense"]["manifest_path"] == str(paths["manifest.json"].resolve())
    assert resolved["retrieval"]["sparse"]["index_path"] == str(tmp_path.resolve())
    assert resolved["retrieval"]["graph"]["path"] == str(paths["graph.pkl"].resolve())
    assert resolved["output"]["root"] == str((tmp_path / "runs").resolve())
    assert resolved["metadata"]["runtime_path_overrides"]["faiss_index"] == str(paths["index.faiss"].resolve())
    assert resolved["metadata"]["runtime_path_overrides"]["bm25_index"] == str(paths["bm25_index.pkl"].resolve())


def test_missing_runtime_override_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="not a file"):
        apply_runtime_path_overrides(_config(), benchmark_source=tmp_path / "missing.jsonl")
    bm25 = tmp_path / "bm25_index.pkl"
    bm25.write_bytes(b"fixture")
    with pytest.raises(Exception, match="requires both"):
        apply_runtime_path_overrides(_config(), bm25_index_source=bm25)


def test_run_modes_do_not_silently_execute_or_downgrade() -> None:
    validate_run_parameters("inspect", smoke_limit=5, existing_run_dir=None)
    source = _cell_containing('if RUN_MODE == "inspect"')
    inspect_branch = source.split("else:", 1)[0]
    assert "run_ablation_config(" not in inspect_branch
    assert "limit=SMOKE_LIMIT if RUN_MODE == \"smoke\" else None" in source
    assert "RUN_MODE = \"inspect\"" in _source()
    assert "fixture" not in source.lower()


def test_export_copies_canonical_files_zips_and_refuses_overwrite(tmp_path: Path) -> None:
    run = tmp_path / "run-1"
    _completed_run(run)
    (run / "index.faiss").write_bytes(b"not exported")
    (run / "benchmark.jsonl").write_text("{}\n", encoding="utf-8")
    result = export_run_artifacts(run, tmp_path / "exports", create_zip=True)
    assert result.archive and result.archive.is_file()
    assert set(result.files) == {
        "manifest.json", "resolved_config.yaml", "e2e_predictions.jsonl",
        "e2e_metrics.json", "latency.json", "errors.jsonl", "report.md",
    }
    assert not (result.directory / "index.faiss").exists()
    assert not (result.directory / "benchmark.jsonl").exists()
    with pytest.raises(ArtifactLoadError, match="refusing to overwrite"):
        export_run_artifacts(run, tmp_path / "exports")


def test_completed_run_missing_mandatory_artifact_is_flagged(tmp_path: Path) -> None:
    run = tmp_path / "run-2"
    _completed_run(run)
    (run / "latency.json").unlink()
    with pytest.raises(ArtifactLoadError, match="missing canonical artifacts"):
        load_run_artifacts(run, require_completed=True)


def test_export_rejects_secret_content(tmp_path: Path) -> None:
    run = tmp_path / "run-3"
    _completed_run(run, secret="do-not-export")
    with pytest.raises(ArtifactLoadError, match="credential"):
        export_run_artifacts(run, tmp_path / "exports", sensitive_values=("do-not-export",))
