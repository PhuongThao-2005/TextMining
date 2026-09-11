from __future__ import annotations

from dataclasses import asdict
from types import ModuleType, SimpleNamespace
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from retrieval.graph_rrf_retriever import GraphRRFGlobalReranker
from retrieval.remote_stages import RemoteCrossEncoder, RemoteGraph
from retrieval.schema import RetrievalResult, RetrievedChunk
from retrieval.stores import SearchHit
from services.graph_reranker_service import create_app
from services.reranker_adapters import (
    BGE_MODEL, MMINILM_MODEL, QWEN3_MODEL, JINA_MODEL, RerankerModelLoadError,
    RerankerRegistry, TrustRemoteCodeDisabledError, UnsupportedRerankerModelError,
    ExperimentalRerankerDisabledError, Qwen3RerankerAdapter,
)


def _chunk(chunk_id: str, text: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        chunk_text=text,
        citation_anchor=chunk_id,
        citation_label=chunk_id,
        title="Fixture",
        article_number="1",
        unit_type="article",
        path=None,
        validity_group="active",
        legal_authority_rank=1,
        vector_score=score,
        rerank_score=score,
        id_str="doc-1",
        parent_unit_id="article-1",
        metadata={"chunk_id": chunk_id, "chunk_text": text},
    )


class _Store:
    def scroll(self, filters, limit):
        assert filters == {"chunk_id": {"in": ["c1", "c3"]}}
        assert limit == 2
        return [
            SearchHit("c1", 0.0, _chunk("c1", "dense and graph", 0.9).metadata),
            SearchHit("c3", 0.0, _chunk("c3", "graph only", 0.0).metadata),
        ]


class _DenseRetriever:
    store = _Store()

    def __init__(self):
        self.kwargs = None

    def retrieve(self, query, **kwargs):
        assert query == "legal question"
        self.kwargs = kwargs
        return RetrievalResult(
            chunks=[_chunk("c1", "dense and graph", 0.9), _chunk("c2", "dense only", 0.8)],
            total_candidates=2,
            filter_profile_used="broad",
        )


class _GraphExpansion:
    def expand(self, seed_ids, *, max_hop, max_context):
        assert seed_ids == ["c1", "c2"]
        assert (max_hop, max_context) == (2, 30)
        return SimpleNamespace(ordered_context_chunks=("c1", "c3"))


class _CrossEncoder:
    def __init__(self):
        self.pairs = None

    def predict(self, pairs):
        self.pairs = pairs
        scores = {"dense and graph": 0.5, "dense only": 0.1, "graph only": 0.9}
        return [scores[text] for _, text in pairs]


def test_dense_graph_rrf_global_reranker_pipeline_and_latency() -> None:
    dense = _DenseRetriever()
    cross_encoder = _CrossEncoder()
    retriever = GraphRRFGlobalReranker(
        dense_retriever=dense,
        graph_expansion=_GraphExpansion(),
        cross_encoder_name="fixture",
        cross_encoder=cross_encoder,
    )

    result, latency = retriever.retrieve_with_latency(
        "legal question", top_k=2, top_n=2, filter_profile="broad", score_threshold=0.3
    )

    assert dense.kwargs == {
        "filter_profile": "broad",
        "top_k": 2,
        "top_n": 2,
        "score_threshold": 0.3,
        "expand_units": False,
    }
    assert [chunk.chunk_id for chunk in result.chunks] == ["c3", "c1"]
    assert result.total_candidates == 3
    assert len(cross_encoder.pairs) == 3
    assert latency.dense_latency_s >= 0
    assert latency.graph_traversal_latency_s >= 0
    assert latency.fusion_latency_s >= 0
    assert latency.rerank_latency_s >= 0
    assert latency.total_latency_s >= 0


def test_remote_graph_hydrates_without_local_store() -> None:
    class Client:
        def request(self, path, payload):
            assert path == "/graph"
            return {"hits": [asdict(_chunk("c3", "graph only", 0.0))]}

    graph = RemoteGraph(Client())
    expansion = graph.expand(["c1"], max_hop=1, max_context=5)
    assert expansion.ordered_context_chunks == ["c3"]
    assert graph.load_chunks(["c3"])[0].citation_anchor == "c3"


def test_remote_reranker_validates_model_and_sends_requested_model() -> None:
    class Client:
        def __init__(self):
            self.payload = None

        def request(self, path, payload):
            assert path == "/rerank"
            self.payload = payload
            return {"model": payload["model"], "scores": [0.7]}

    client = Client()
    reranker = RemoteCrossEncoder(client, expected_model="fixture")
    assert reranker.predict([("question", "answer")]) == [0.7]
    assert client.payload == {"query": "question", "texts": ["answer"], "model": "fixture"}
    with pytest.raises(ValueError, match="one query"):
        reranker.predict([("q1", "a1"), ("q2", "a2")])


def test_reranker_api_requires_auth_preserves_order_and_accepts_model(monkeypatch) -> None:
    class Engine:
        identity = {"model": "fixture", "loaded_models": []}

        def run(self, request):
            model = request.model or "fixture"
            return {"model": model, "scores": list(range(len(request.texts)))}

    monkeypatch.setenv("RERANKER_API_KEY", "secret")
    with TestClient(create_app("reranker", Engine)) as client:
        assert client.get("/readyz").status_code == 401
        response = client.post(
            "/rerank",
            headers={"Authorization": "Bearer secret"},
            json={"query": "q", "texts": ["a", "b"], "model": "BAAI/bge-reranker-v2-m3"},
        )
    body = response.json()
    assert body["scores"] == [0, 1]
    assert body["model"] == "BAAI/bge-reranker-v2-m3"


def test_reranker_engine_lazy_loads_requested_models(monkeypatch) -> None:
    from services.graph_reranker_service import RerankerEngine, RerankRequest

    loaded: list[str] = []

    class FakeCrossEncoder:
        def __init__(self, name, *, device, max_length):
            loaded.append(name)
            self.name = name

        def predict(self, pairs, *, batch_size, show_progress_bar):
            return [float(index) for index, _ in enumerate(pairs)]

    fake_module = ModuleType("sentence_transformers")
    fake_module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("RERANKER_DEFAULT_MODEL", MMINILM_MODEL)
    monkeypatch.setenv("RERANKER_MODEL_CACHE_SIZE", "2")
    monkeypatch.setenv("RERANKER_DEVICE", "cpu")

    engine = RerankerEngine()
    first = engine.run(RerankRequest(query="q", texts=["a"], model=MMINILM_MODEL))
    second = engine.run(RerankRequest(query="q", texts=["a", "b"], model=MMINILM_MODEL))
    third = engine.run(RerankRequest(query="q", texts=["a"], model=BGE_MODEL))

    assert first["model"] == second["model"] == MMINILM_MODEL
    assert third["model"] == BGE_MODEL
    assert second["scores"] == [0.0, 1.0]
    assert loaded == [MMINILM_MODEL, BGE_MODEL]
    assert engine.identity["loaded_models"] == [MMINILM_MODEL, BGE_MODEL]


def test_reranker_registry_rejects_unsupported_and_disabled_experimental_models() -> None:
    registry = RerankerRegistry(
        default_model=MMINILM_MODEL, device="cpu", batch_size=1, max_length=32, cache_size=2,
        allow_experimental=False, trust_remote_code=False,
        factories={MMINILM_MODEL: lambda: SimpleNamespace(rerank=lambda *args, **kwargs: [])},
    )

    assert registry.get(MMINILM_MODEL) is registry.get("mMiniLM")
    with pytest.raises(UnsupportedRerankerModelError):
        registry.get("unknown-model")
    with pytest.raises(ExperimentalRerankerDisabledError):
        registry.get(QWEN3_MODEL)


def test_reranker_registry_allows_mocked_experimental_adapter() -> None:
    adapter = SimpleNamespace(rerank=lambda query, documents, top_k=None: [
        {"index": 0, "score": 1.0, "text": documents[0]}
    ])
    registry = RerankerRegistry(
        default_model=MMINILM_MODEL, device="cpu", batch_size=1, max_length=32, cache_size=2,
        allow_experimental=True, trust_remote_code=False, factories={QWEN3_MODEL: lambda: adapter},
    )

    assert registry.get(QWEN3_MODEL) is adapter


def test_jina_requires_explicit_trust_remote_code() -> None:
    registry = RerankerRegistry(
        default_model=MMINILM_MODEL, device="cpu", batch_size=1, max_length=32, cache_size=2,
        allow_experimental=True, trust_remote_code=False,
    )

    with pytest.raises(TrustRemoteCodeDisabledError):
        registry.get(JINA_MODEL)


def test_qwen_adapter_rejects_random_score_weight_warning(monkeypatch) -> None:
    class FakeCrossEncoder:
        def __init__(self, *args, **kwargs):
            logging.getLogger("transformers.modeling_utils").warning(
                "Some weights of Qwen3ForSequenceClassification were not initialized from "
                "the model checkpoint and are newly initialized: ['score.weight']"
            )

        def predict(self, pairs, *, batch_size, show_progress_bar):
            return [0.1 for _ in pairs]

    fake_module = ModuleType("sentence_transformers")
    fake_module.CrossEncoder = FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    with pytest.raises(RerankerModelLoadError) as exc_info:
        Qwen3RerankerAdapter(QWEN3_MODEL, device="cpu", max_length=32, batch_size=1)
    assert "score.weight" in str(exc_info.value.root_cause)


def test_reranker_api_returns_structured_model_errors(monkeypatch) -> None:
    class Engine:
        identity = {"model": "fixture", "loaded_models": []}

        def run(self, request):
            raise RerankerModelLoadError(request.model or JINA_MODEL, "missing dependency")

    monkeypatch.setenv("RERANKER_API_KEY", "secret")
    with TestClient(create_app("reranker", Engine)) as client:
        response = client.post(
            "/rerank",
            headers={"Authorization": "Bearer secret"},
            json={"query": "q", "texts": ["a"], "model": JINA_MODEL},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "error": "model_load_failed",
        "message": f"Failed to load reranker model {JINA_MODEL!r}.",
        "model": JINA_MODEL,
        "root_cause": "missing dependency",
    }


def test_reranker_api_returns_400_for_unsupported_model(monkeypatch) -> None:
    from services.graph_reranker_service import RerankerEngine

    monkeypatch.setenv("RERANKER_API_KEY", "secret")
    monkeypatch.setenv("RERANKER_DEFAULT_MODEL", MMINILM_MODEL)
    with TestClient(create_app("reranker", RerankerEngine)) as client:
        response = client.post(
            "/rerank",
            headers={"Authorization": "Bearer secret"},
            json={"query": "q", "texts": ["a"], "model": "unknown-model"},
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "unsupported_model"
    assert detail["model"] == "unknown-model"
    assert MMINILM_MODEL in detail["supported_models"]


def test_runner_builds_remote_graph_and_reranker_without_local_models(
    monkeypatch,
) -> None:
    import scripts.run_ablation_config as runner
    from service.qa_service import (
        _enable_global_reranker,
        _enable_graph_stack,
        load_ui_config_registry,
    )

    monkeypatch.setenv("GRAPH_SERVICE_URL", "http://graph")
    monkeypatch.setenv("GRAPH_API_KEY", "key")
    monkeypatch.setenv("RERANKER_SERVICE_URL", "http://reranker")
    monkeypatch.setenv("RERANKER_API_KEY", "key")
    config = load_ui_config_registry()["Agent-None-RemoteDense"]
    _enable_graph_stack(config["retrieval"])
    _enable_global_reranker(config["retrieval"])
    config["retrieval"]["fusion"] = {
        "enabled": True,
        "strategy": "rrf",
        "rrf_k": 60,
    }
    monkeypatch.setattr(
        runner,
        "build_vector_retriever",
        lambda runtime: SimpleNamespace(retrieve=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(runner, "_build_generator", lambda config: (None, []))
    monkeypatch.setattr(runner, "_build_judge", lambda config: (None, []))

    pipeline, _, _, _ = runner.build_ablation_stack(config)

    assert isinstance(pipeline.graph_expansion, RemoteGraph)
    assert isinstance(pipeline._cross_encoder, RemoteCrossEncoder)
    assert pipeline.chunk_loader is not None
