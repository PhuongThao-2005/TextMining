"""Unit tests for the FAISS-backed retriever_factory extension (FR-002a)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import evaluation.retriever_factory as retriever_factory
from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever
from retrieval import BM25RemoteRetriever, VectorRetriever
from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore
from retrieval.stores import InMemoryVectorStore, QdrantVectorStore


class _FakeEmbedder:
    """Stand-in for SentenceTransformerEmbedder that avoids network/model downloads.

    These tests exercise the *store*-construction branch of build_vector_retriever
    (faiss / qdrant / unknown-value handling), which is independent of embedder
    choice; the real SentenceTransformerEmbedder requires the optional
    sentence-transformers dependency and downloads a model on first use, so it
    is monkeypatched out here.
    """

    def __init__(self, *args, **kwargs) -> None:
        pass


class _FakeQdrantStore:
    """Stand-in for QdrantVectorStore that avoids requiring the qdrant-client package."""

    def __init__(self, *args, **kwargs) -> None:
        pass


@pytest.fixture()
def fake_sentence_transformer_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retriever_factory, "SentenceTransformerEmbedder", _FakeEmbedder)


@pytest.fixture()
def fake_qdrant_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retriever_factory, "QdrantVectorStore", _FakeQdrantStore)


def _write_payloads(path: Path, payloads: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _make_index_fixture(tmp_path: Path, n: int = 3, dim: int = 8) -> Path:
    faiss = pytest.importorskip("faiss")
    rng = np.random.default_rng(0)
    vectors = rng.standard_normal((n, dim), dtype=np.float32)
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    payloads = [
        {
            "chunk_id": f"chunk-{i}",
            "parent_unit_id": f"parent-{i // 2}",
            "chunk_index_in_unit": (i % 2) + 1,
            "id_str": f"doc-{i}",
            "chunk_text": f"text-{i}",
            "title": f"Title {i}",
            "citation_anchor": f"Art.{i}",
            "validity_group": "current",
            "unit_type": "article",
            "legal_authority_rank": i + 1,
        }
        for i in range(n)
    ]
    index_dir = tmp_path / "faiss_index"
    index_dir.mkdir()
    faiss.write_index(index, str(index_dir / "index.faiss"))
    _write_payloads(index_dir / "payloads.jsonl", payloads)
    return index_dir


def test_faiss_store_builds_retriever_backed_by_sqlite_faiss_store(
    tmp_path: Path, fake_sentence_transformer_embedder: None
) -> None:
    """store='faiss' with a valid index_dir constructs a VectorRetriever over SQLitePayloadFaissVectorStore."""
    index_dir = _make_index_fixture(tmp_path)
    runtime = RetrieverRuntimeConfig(store="faiss", index_dir=index_dir, dev_hashing=False, model="dummy-model")

    retriever = build_vector_retriever(runtime)

    assert isinstance(retriever, VectorRetriever)
    assert isinstance(retriever.store, SQLitePayloadFaissVectorStore)


def test_faiss_store_missing_index_dir_raises_clear_error(
    tmp_path: Path, fake_sentence_transformer_embedder: None
) -> None:
    """A missing/incomplete index_dir must raise a clear, actionable FileNotFoundError (FR-012)."""
    missing_dir = tmp_path / "does_not_exist"
    runtime = RetrieverRuntimeConfig(store="faiss", index_dir=missing_dir, dev_hashing=False, model="dummy-model")

    with pytest.raises(FileNotFoundError) as exc_info:
        build_vector_retriever(runtime)

    message = str(exc_info.value)
    assert str(missing_dir) in message
    assert "INDEX_DIR" in message


def test_qdrant_store_regression_still_builds_qdrant_backed_retriever(
    fake_sentence_transformer_embedder: None,
    fake_qdrant_store: None,
) -> None:
    """The existing store='qdrant' branch must remain functional (regression coverage)."""
    runtime = RetrieverRuntimeConfig(
        store="qdrant",
        qdrant_url="http://localhost:6333",
        collection_name="legal_chunks",
        dev_hashing=False,
        model="dummy-model",
    )

    retriever = build_vector_retriever(runtime)

    assert isinstance(retriever, VectorRetriever)
    assert isinstance(retriever.store, _FakeQdrantStore)


def test_dev_hashing_regression_still_builds_in_memory_retriever() -> None:
    """The existing dev_hashing=True smoke-test branch must remain functional (regression coverage)."""
    runtime = RetrieverRuntimeConfig(store="faiss", index_dir="unused", dev_hashing=True, model="dummy-model")

    retriever = build_vector_retriever(runtime)

    assert isinstance(retriever, VectorRetriever)
    assert isinstance(retriever.store, InMemoryVectorStore)


def test_bm25_backend_builds_remote_retriever_with_qdrant_payload_store(
    fake_qdrant_store: None,
) -> None:
    runtime = RetrieverRuntimeConfig(
        backend="bm25",
        store="qdrant",
        bm25_service_url="https://bm25.example.test",
        bm25_api_key="test-key",
    )

    retriever = build_vector_retriever(runtime)

    assert isinstance(retriever, BM25RemoteRetriever)
    assert isinstance(retriever.payload_store, _FakeQdrantStore)
    assert retriever.client.base_url == "https://bm25.example.test"


def test_unknown_store_value_raises_value_error(fake_sentence_transformer_embedder: None) -> None:
    """An unrecognized store value must raise a clear ValueError rather than silently defaulting."""
    runtime = RetrieverRuntimeConfig(store="not-a-real-store", dev_hashing=False, model="dummy-model")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        build_vector_retriever(runtime)


def test_dimension_mismatch_is_rejected_before_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    class DimensionEmbedder:
        dimension = 8

        def __init__(self, *args, **kwargs) -> None:
            pass

    class DimensionStore:
        dimension = 7

        @classmethod
        def load(cls, index_dir: Path):
            del index_dir
            return cls()

    monkeypatch.setattr(retriever_factory, "SentenceTransformerEmbedder", DimensionEmbedder)
    monkeypatch.setattr(retriever_factory, "SQLitePayloadFaissVectorStore", DimensionStore)
    runtime = RetrieverRuntimeConfig(store="faiss", index_dir="fixture", model="fixture-model")

    with pytest.raises(ValueError, match="dimension mismatch"):
        build_vector_retriever(runtime)
