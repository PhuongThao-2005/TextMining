from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

import services.bm25_service as service
from retrieval.stores import SearchHit


class _Request:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


@dataclass
class _FakeRetriever:
    total_documents: int
    hits: list[SearchHit]
    calls: list[tuple[str, int]] = field(default_factory=list)

    def search(self, query: str, *, top_k: int = 20) -> list[SearchHit]:
        self.calls.append((query, top_k))
        return self.hits[:top_k]


@pytest.fixture(autouse=True)
def _reset_service_cache(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "_index", None)
    monkeypatch.delenv("BM25_API_KEY", raising=False)
    yield
    monkeypatch.setattr(service, "_index", None)


def _write_shard(root: Path, name: str, *, include_metadata: bool = True) -> Path:
    shard_dir = root / name
    shard_dir.mkdir(parents=True)
    (shard_dir / "bm25_index.pkl").write_bytes(b"index")
    if include_metadata:
        (shard_dir / "bm25_metadata.pkl").write_bytes(b"metadata")
    (shard_dir / "manifest.json").write_text("{}", encoding="utf-8")
    return shard_dir


def _hit(chunk_id: str, score: float, *, point_id: str | None = None) -> SearchHit:
    return SearchHit(
        point_id=point_id or chunk_id,
        score=score,
        payload={"chunk_id": chunk_id, "chunk_text": f"text for {chunk_id}"},
    )


def test_discover_shards_sorts_and_validates(tmp_path: Path) -> None:
    _write_shard(tmp_path, "shard_02")
    _write_shard(tmp_path, "shard_00")
    _write_shard(tmp_path, "shard_01")

    specs = service._discover_shard_specs(tmp_path)

    assert [spec.name for spec in specs] == ["shard_00", "shard_01", "shard_02"]
    assert [spec.shard_id for spec in specs] == [0, 1, 2]


def test_discover_missing_shard_files_fails_clearly(tmp_path: Path) -> None:
    _write_shard(tmp_path, "shard_00", include_metadata=False)

    with pytest.raises(FileNotFoundError, match="bm25_metadata.pkl"):
        service._discover_shard_specs(tmp_path)


def test_single_index_layout_still_supported(tmp_path: Path) -> None:
    (tmp_path / "bm25_index.pkl").write_bytes(b"index")
    (tmp_path / "bm25_metadata.pkl").write_bytes(b"metadata")

    specs = service._discover_shard_specs(tmp_path)

    assert len(specs) == 1
    assert specs[0].path == tmp_path
    assert specs[0].shard_id == 0


def test_healthz_loads_shards_once_and_sums_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_shard(tmp_path, "shard_00")
    _write_shard(tmp_path, "shard_01")
    retrievers = {
        "shard_00": _FakeRetriever(10, []),
        "shard_01": _FakeRetriever(20, []),
    }
    load_calls: list[str] = []

    def fake_load(path: Path) -> _FakeRetriever:
        load_calls.append(path.name)
        return retrievers[path.name]

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr(service.BM25SparseRetriever, "load", staticmethod(fake_load))

    first = service.healthz(_Request())
    second = service.healthz(_Request())

    assert first["status"] == "ok"
    assert first["shard_count"] == 2
    assert first["total_documents"] == 30
    assert second["total_documents"] == 30
    assert load_calls == ["shard_00", "shard_01"]


def test_bm25_search_queries_every_shard_merges_top_k_and_deduplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_shard(tmp_path, "shard_00")
    _write_shard(tmp_path, "shard_01")
    _write_shard(tmp_path, "shard_09")
    retrievers = {
        "shard_00": _FakeRetriever(2, [_hit("a", 4.0), _hit("dup", 3.0)]),
        "shard_01": _FakeRetriever(2, [_hit("dup", 9.0), _hit("b", 2.0)]),
        "shard_09": _FakeRetriever(1, [_hit("c", 7.0)]),
    }

    def fake_load(path: Path) -> _FakeRetriever:
        return retrievers[path.name]

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setenv("BM25_INDEX_VERSION", "test-sharded")
    monkeypatch.setattr(service.BM25SparseRetriever, "load", staticmethod(fake_load))

    response = asyncio.run(
        service.bm25(
            {
                "input": {
                    "queries": [{"qa_id": "q1", "question": "nghi hang nam"}],
                    "bm25_top_k": 3,
                    "include_payloads": True,
                    "include_diagnostics": True,
                }
            },
            _Request(),
        )
    )

    hits = response["results"][0]["bm25_hits"]
    assert [hit["chunk_id"] for hit in hits] == ["dup", "c", "a"]
    assert hits[0]["bm25_score"] == 9.0
    assert hits[0]["shard_id"] == 1
    assert hits[0]["shard_name"] == "shard_01"
    assert hits[0]["shard_rank"] == 1
    assert "local_index" not in hits[0]
    assert hits[0]["payload"]["chunk_text"] == "text for dup"
    assert response["index_version"] == "test-sharded"
    assert response["diagnostics"]["shard_count"] == 3
    assert response["diagnostics"]["total_documents"] == 5
    for retriever in retrievers.values():
        assert retriever.calls == [("nghi hang nam", 3)]


def test_auth_still_requires_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BM25_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc_info:
        service._require_auth(_Request({"authorization": "Bearer wrong"}))

    assert exc_info.value.status_code == 401
