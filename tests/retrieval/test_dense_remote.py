"""Exercise real FAISS + SQLite through HTTP using a tiny offline embedder."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Event

import faiss
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from retrieval.config import VectorIndexConfig
from retrieval.dense_client import DenseRemoteRetriever, DenseServiceError
from retrieval.embeddings import HashingEmbedder
from retrieval.retriever import VectorRetriever
from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore, _ensure_payload_cache
from services.dense_service import create_app, load_runtime


@pytest.fixture
def bundle(tmp_path):
    rows = []
    for index, (text, validity) in enumerate([
        ("người lao động nghỉ phép", "active"),
        ("nghỉ phép năm tiền lương", "expired"),
        ("hợp đồng lao động", "future"),
        ("thuế doanh nghiệp", "unknown"),
    ]):
        rows.append(dict(chunk_id=f"c{index}", chunk_text=text, citation_anchor=f"Điều {index + 1}",
            citation_label="Luật lao động", title="Luật lao động", article_number=str(index + 1),
            unit_type="article", path="law.txt", validity_group=validity, legal_authority_rank=1,
            id_str="law", parent_unit_id="unit", chunk_index_in_unit=index + 1))
    payload_path = tmp_path / "payloads.jsonl"
    payload_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    embedder = HashingEmbedder()
    index = faiss.IndexFlatIP(embedder.dimension)
    index.add(np.array(embedder.encode_passages([row["chunk_text"] for row in rows]), dtype=np.float32))
    faiss.write_index(index, str(tmp_path / "index.faiss"))
    _ensure_payload_cache(payload_path, tmp_path / "payload_cache.sqlite")
    manifest = dict(embedding_model="intfloat/multilingual-e5-large", index_version="chunk-metadata-faiss-v1",
        corpus_version="pre-processed-v1", payload_count=len(rows))
    (tmp_path / "index_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


@pytest.fixture
def runtime(bundle, monkeypatch):
    monkeypatch.setenv("DENSE_INDEX_DIR", str(bundle))
    monkeypatch.setenv("DENSE_EXPECTED_DIMENSION", "384")
    monkeypatch.setattr("retrieval.embeddings.SentenceTransformerEmbedder", lambda *args, **kwargs: HashingEmbedder())
    return load_runtime()


def remote_client(transport, **kwargs):
    return DenseRemoteRetriever(base_url="http://dense.test", api_key="test-key", expected_dimension=384,
                                transport=transport, max_retries=0, **kwargs)


def bridge(api):
    def handle(request):
        response = api.request(request.method, request.url.path, headers=request.headers, content=request.content)
        return httpx.Response(response.status_code, content=response.content, headers=response.headers)
    return httpx.MockTransport(handle)


@pytest.mark.parametrize("profile", ["broad", "current_law", "historical"])
@pytest.mark.parametrize("expand", [False, True])
def test_local_remote_parity(runtime, profile, expand):
    retriever, identity = runtime
    expected = retriever.retrieve("nghỉ phép", filter_profile=profile, top_k=4, top_n=3,
                                  score_threshold=-1.0, expand_units=expand)
    with TestClient(create_app(lambda: runtime, api_key="test-key")) as api:
        remote = remote_client(bridge(api))
        assert remote.check_ready() == identity
        actual = remote.retrieve("nghỉ phép", filter_profile=profile, top_k=4, top_n=3,
                                 score_threshold=-1.0, expand_units=expand)
        assert asdict(actual) == asdict(expected)
        assert remote.last_diagnostics["latency_ms"]["embedding"] >= 0


@pytest.mark.parametrize("body", [
    {"query": " "}, {"query": "x" * 8001}, {"query": "q", "top_k": 0},
    {"query": "q", "top_k": True}, {"query": "q", "top_k": 2, "top_n": 3},
    {"query": "q", "filter_profile": "graph_guided"}, {"query": "q", "extra_filters": {}},
])
def test_invalid_requests(runtime, body):
    with TestClient(create_app(lambda: runtime, api_key="test-key")) as api:
        response = api.post("/search", json=body, headers={"Authorization": "Bearer test-key"})
        assert response.status_code == 422
        assert response.json()["error"] == "invalid_request"


def test_auth_readiness_and_empty_results(runtime):
    app = create_app(lambda: runtime, api_key="test-key")
    with TestClient(app) as api:
        for endpoint in ("/healthz", "/readyz", "/version"):
            assert api.get(endpoint).status_code == 401
        assert api.post("/search", json={"query": "q"}).status_code == 401
        remote = remote_client(bridge(api))
        result = remote.retrieve("unrelatedxyz", top_k=4, top_n=3, score_threshold=1.0)
        assert result.chunks == []
        app.state.ready = False
        with pytest.raises(DenseServiceError, match="not ready"):
            remote.check_ready()


def test_busy_service_rejects_concurrent_search(runtime, monkeypatch):
    retriever, _ = runtime
    started, release = Event(), Event()
    original = retriever.retrieve

    def slow(*args, **kwargs):
        started.set()
        assert release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(retriever, "retrieve", slow)
    with TestClient(create_app(lambda: runtime, api_key="test-key")) as api:
        def search():
            return api.post("/search", json={"query": "nghỉ phép"}, headers={"Authorization": "Bearer test-key"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(search)
            try:
                assert started.wait(5)
                assert search().status_code == 429
            finally:
                release.set()
            assert first.result().status_code == 200


@pytest.mark.parametrize("mutation", ["identity", "citation", "request_id", "json"])
def test_client_rejects_bad_response(runtime, mutation):
    with TestClient(create_app(lambda: runtime, api_key="test-key")) as api:
        def handle(request):
            payload = api.post("/search", content=request.content, headers=request.headers).json()
            if mutation == "identity":
                payload["embedding_model"] = "wrong-model"
            elif mutation == "citation":
                del payload["hits"][0]["citation_anchor"]
            elif mutation == "request_id":
                payload["request_id"] = "wrong-request"
            else:
                return httpx.Response(200, text="not-json")
            return httpx.Response(200, json=payload)
        with pytest.raises(DenseServiceError):
            remote_client(httpx.MockTransport(handle)).retrieve("nghỉ phép", score_threshold=-1.0)


@pytest.mark.parametrize("status,retries", [(503, 2), (429, 2), (401, 0), (422, 0)])
def test_retries_are_bounded(status, retries, monkeypatch):
    calls = []
    monkeypatch.setattr("retrieval.dense_client.time.sleep", lambda _: None)
    def handle(request):
        calls.append(request)
        return httpx.Response(status)
    remote = remote_client(httpx.MockTransport(handle))
    remote.max_retries = 2
    with pytest.raises(DenseServiceError):
        remote.check_ready()
    assert len(calls) == retries + 1


def test_timeout_has_safe_error():
    def handle(request):
        raise httpx.ReadTimeout("secret-token", request=request)
    with pytest.raises(DenseServiceError, match="timed out") as caught:
        remote_client(httpx.MockTransport(handle)).check_ready()
    assert "secret-token" not in str(caught.value)


def test_missing_cache_never_rebuilt(bundle):
    cache = bundle / "payload_cache.sqlite"
    cache.unlink()
    with pytest.raises(ValueError, match="prebuilt"):
        SQLitePayloadFaissVectorStore.load(bundle, require_existing_cache=True)
    assert not cache.exists()


def test_copied_cache_is_readonly_and_reused(bundle):
    payloads = bundle / "payloads.jsonl"
    cache = bundle / "payload_cache.sqlite"
    original = cache.read_bytes()
    os.utime(payloads, (1000000, 1000000))
    store = SQLitePayloadFaissVectorStore.load(bundle, require_existing_cache=True)
    try:
        import sqlite3
        with pytest.raises(sqlite3.OperationalError):
            store.conn.execute("DELETE FROM payloads")
    finally:
        store.conn.close()
    assert cache.read_bytes() == original


def test_manifest_mismatch_fails_startup(bundle, monkeypatch):
    monkeypatch.setenv("DENSE_INDEX_DIR", str(bundle))
    monkeypatch.setenv("DENSE_EXPECTED_MODEL", "wrong")
    with pytest.raises(ValueError, match="identity"):
        with TestClient(create_app()):
            pass
