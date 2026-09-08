"""Remote mode must not depend on local model/index files."""
from copy import deepcopy

import pytest

from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever
from retrieval.dense_client import DenseRemoteRetriever, DenseServiceError
from scripts.run_ablation_config import AblationConfigError, build_ablation_stack, validate_ablation_config
from service.qa_service import QuestionRequest, UIConfigError, apply_safe_overrides, load_ui_config_registry, run_preflight


@pytest.fixture
def config():
    return deepcopy(load_ui_config_registry()["Dense-Remote-E2E"])


def test_remote_factory_does_not_load_local_store(tmp_path, monkeypatch):
    def reject(*args, **kwargs):
        pytest.fail("Remote dense attempted to load local FAISS")
    monkeypatch.setattr("evaluation.retriever_factory.SQLitePayloadFaissVectorStore.load", reject)
    remote = build_vector_retriever(RetrieverRuntimeConfig(backend="dense_remote", index_dir=tmp_path,
        dense_remote_options={"base_url": "http://dense.test"}))
    assert isinstance(remote, DenseRemoteRetriever)


def test_ablation_builds_remote_without_artifacts(config, tmp_path, monkeypatch):
    monkeypatch.setenv("DENSE_SERVICE_URL", "http://dense.test")
    monkeypatch.setenv("DENSE_API_KEY", "private-test-key")
    monkeypatch.setattr("scripts.run_ablation_config._build_generator", lambda _: (lambda *args: "", []))
    retriever, _, _, secrets = build_ablation_stack(config, project_root=tmp_path)
    assert isinstance(retriever, DenseRemoteRetriever)
    assert retriever.expected["index_version"] == config["retrieval"]["dense"]["index_version"]
    assert "private-test-key" in secrets


def test_preflight_checks_remote_without_local_artifacts(config, tmp_path, monkeypatch):
    calls = []
    def ready(self):
        calls.append(self.base_url)
        return self.expected
    monkeypatch.setattr(DenseRemoteRetriever, "check_ready", ready)
    result = run_preflight(config, config_name="Dense-Remote-E2E", project_root=tmp_path,
        environ={"DENSE_SERVICE_URL": "http://dense.test", "LLM_BASE_MODEL": "test", "LLM_API_KEY": "test", "LLM_BASE_URL": "http://llm.test"},
        package_available=lambda _: True)
    assert result.runnable, result.blockers
    assert calls == ["http://dense.test"]
    assert not any(check.name.startswith("faiss") for check in result.checks)


def test_preflight_reports_remote_auth_failure(config, tmp_path, monkeypatch):
    def fail(self):
        raise DenseServiceError("Dense service authentication failed.")
    monkeypatch.setattr(DenseRemoteRetriever, "check_ready", fail)
    result = run_preflight(config, config_name="Dense-Remote-E2E", project_root=tmp_path,
        environ={"DENSE_SERVICE_URL": "http://dense.test", "LLM_BASE_MODEL": "test", "LLM_API_KEY": "test"},
        package_available=lambda _: True)
    assert not result.runnable
    assert "Dense service authentication failed." in result.blockers


@pytest.mark.parametrize("component", ["sparse", "graph", "fusion", "reranker"])
def test_remote_rejects_unsupported_combinations(config, component):
    config["retrieval"][component]["enabled"] = True
    with pytest.raises(AblationConfigError, match="Remote dense v1"):
        validate_ablation_config(config, config_name="Dense-Remote-E2E")
    with pytest.raises(UIConfigError, match="Dense remote v1"):
        apply_safe_overrides(config, QuestionRequest("question", "Dense-Remote-E2E"))
