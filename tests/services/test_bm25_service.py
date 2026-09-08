from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import HTTPException

import services.bm25_service as service


class _Request:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


@dataclass
class _FakeBM25:
    scores: list[float]
    calls: list[list[str]]

    def get_scores(self, tokenized_query: list[str]) -> list[float]:
        self.calls.append(list(tokenized_query))
        return self.scores


@dataclass
class _FakePayloadLookup:
    calls: list[list[str]]
    path: Path = Path("fake-payload-cache.sqlite")

    def load_payloads(self, chunk_ids):
        ids = list(chunk_ids)
        self.calls.append(ids)
        return {
            chunk_id: {"chunk_id": chunk_id, "chunk_text": f"text for {chunk_id}"}
            for chunk_id in ids
        }


@dataclass
class _ValidityPayloadLookup:
    payloads: dict[str, dict[str, str]]
    calls: list[list[str]]
    path: Path = Path("fake-payload-cache.sqlite")

    def load_payloads(self, chunk_ids):
        ids = list(chunk_ids)
        self.calls.append(ids)
        return {chunk_id: self.payloads[chunk_id] for chunk_id in ids if chunk_id in self.payloads}


@pytest.fixture(autouse=True)
def _reset_service(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "_index", None)
    monkeypatch.delenv("BM25_API_KEY", raising=False)
    monkeypatch.delenv("BM25_SEARCH_WORKERS", raising=False)
    monkeypatch.delenv("BM25_PAYLOAD_CACHE_PATH", raising=False)
    monkeypatch.delenv("DENSE_INDEX_DIR", raising=False)
    monkeypatch.setattr(service, "_current_rss_bytes", lambda: 123456)
    yield
    monkeypatch.setattr(service, "_index", None)


def _write_shard(
    root: Path,
    name: str,
    *,
    include_metadata: bool = True,
    chunk_ids: list[str] | None = None,
    document_count: int | None = None,
) -> Path:
    shard_dir = root / name
    shard_dir.mkdir(parents=True)
    (shard_dir / "bm25_index.pkl").write_bytes(b"index")
    if include_metadata:
        (shard_dir / "bm25_metadata.pkl").write_bytes(b"metadata")
    if chunk_ids is not None:
        lines = [json.dumps(chunk_id) for chunk_id in chunk_ids]
        (shard_dir / "bm25_chunk_ids.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {} if document_count is None else {"document_count": document_count}
    (shard_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return shard_dir


def _metadata(name: str, scores: list[float]) -> dict[str, list[dict[str, str]] | list[str]]:
    chunk_ids = [f"{name}-chunk-{index}" for index in range(len(scores))]
    payloads = [
        {"chunk_id": chunk_id, "chunk_text": f"text for {chunk_id}"}
        for chunk_id in chunk_ids
    ]
    return {"chunk_ids": chunk_ids, "payloads": payloads}


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


def test_healthz_does_not_preload_when_startup_has_not_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_shard(tmp_path, "shard_00", document_count=10)
    _write_shard(tmp_path, "shard_01", document_count=20)
    load_calls: list[str] = []

    def fake_load(path: Path):
        load_calls.append(path.name)
        raise AssertionError("/healthz must not load BM25 indexes")

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr(service, "_load_bm25_index", fake_load)

    response = service.healthz(_Request())

    assert response["status"] == "starting"
    assert response["shard_count"] == 2
    assert response["total_documents"] == 30
    assert response["resident_index_count"] == 0
    assert response["preload_seconds"] is None
    assert load_calls == []


def test_preloads_all_ten_indexes_once_and_reuses_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores_by_name = {f"shard_{idx:02d}": [float(idx + 1), 0.1] for idx in range(10)}
    indexes: dict[str, _FakeBM25] = {}
    index_load_calls: list[str] = []
    payload_lookup = _FakePayloadLookup(calls=[])

    for name, scores in scores_by_name.items():
        _write_shard(
            tmp_path,
            name,
            chunk_ids=_metadata(name, scores)["chunk_ids"],
            document_count=len(scores),
        )
        indexes[name] = _FakeBM25(scores=scores, calls=[])

    def fake_load_index(path: Path) -> _FakeBM25:
        index_load_calls.append(path.name)
        return indexes[path.name]

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setenv("BM25_INDEX_VERSION", "test-sharded")
    monkeypatch.setattr(service, "_get_tokenizer", lambda: lambda text: text.split())
    monkeypatch.setattr(service, "_load_bm25_index", fake_load_index)
    monkeypatch.setattr(service, "_load_metadata", lambda path: pytest.fail("metadata must not load during resident queries"))
    monkeypatch.setattr(service, "_open_payload_lookup", lambda index_dir: payload_lookup)

    service._load_index()
    first = asyncio.run(_query(top_k=3, include_payloads=True, include_diagnostics=True))
    second = asyncio.run(_query(top_k=3, include_payloads=False, include_diagnostics=True))

    assert index_load_calls == [f"shard_{idx:02d}" for idx in range(10)]
    assert service._index is not None
    assert service._index.resident_index_count == 10
    assert first["diagnostics"]["resident_index_count"] == 10
    assert first["diagnostics"]["startup_preload_seconds"] >= 0
    assert first["diagnostics"]["rss_after_preload_bytes"] == 123456
    assert first["diagnostics"]["search_workers"] == 4
    assert len(first["diagnostics"]["queries"][0]["per_shard_search_seconds"]) == 10
    assert "chunk_id_lookup_seconds" in first["diagnostics"]["queries"][0]
    assert "payload_hydration_seconds" in first["diagnostics"]["queries"][0]
    assert "metadata_hydration_seconds" in first["diagnostics"]["queries"][0]
    assert second["diagnostics"]["resident_index_count"] == 10
    assert index_load_calls == [f"shard_{idx:02d}" for idx in range(10)]
    assert payload_lookup.calls == [[
        "shard_09-chunk-0",
        "shard_08-chunk-0",
        "shard_07-chunk-0",
    ]]
    for bm25 in indexes.values():
        assert bm25.calls == [["nghi", "hang", "nam"], ["nghi", "hang", "nam"]]


def test_response_contract_and_ranking_are_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores_by_name = {
        "shard_00": [0.0, 4.0, 3.0],
        "shard_01": [9.0, 2.0, 0.0],
        "shard_09": [7.0, 0.0, 1.0],
    }
    for name, scores in scores_by_name.items():
        _write_shard(tmp_path, name, chunk_ids=_metadata(name, scores)["chunk_ids"])

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setenv("BM25_INDEX_VERSION", "test-sharded")
    monkeypatch.setattr(service, "_get_tokenizer", lambda: lambda text: text.split())
    monkeypatch.setattr(
        service,
        "_load_bm25_index",
        lambda path: _FakeBM25(scores=scores_by_name[path.name], calls=[]),
    )
    monkeypatch.setattr(service, "_open_payload_lookup", lambda index_dir: _FakePayloadLookup(calls=[]))

    response = asyncio.run(_query(top_k=3, include_payloads=True, include_diagnostics=False))

    hits = response["results"][0]["bm25_hits"]
    assert response == {
        "index_version": "test-sharded",
        "results": [{"qa_id": "q1", "bm25_hits": hits}],
    }
    assert [hit["chunk_id"] for hit in hits] == [
        "shard_01-chunk-0",
        "shard_09-chunk-0",
        "shard_00-chunk-1",
    ]
    assert [hit["bm25_score"] for hit in hits] == [9.0, 7.0, 4.0]
    assert hits[0]["rank"] == 1
    assert hits[0]["shard_id"] == 1
    assert hits[0]["shard_name"] == "shard_01"
    assert hits[0]["shard_rank"] == 1
    assert "local_index" not in hits[0]
    assert hits[0]["payload"]["chunk_text"] == "text for shard_01-chunk-0"


def test_tied_scores_are_ranked_by_chunk_id_after_lazy_hydration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores_by_name = {
        "shard_00": [5.0],
        "shard_01": [5.0],
        "shard_02": [4.0],
    }
    chunk_ids_by_name = {
        "shard_00": ["z-chunk"],
        "shard_01": ["a-chunk"],
        "shard_02": ["m-chunk"],
    }
    for name in scores_by_name:
        _write_shard(tmp_path, name, chunk_ids=chunk_ids_by_name[name])

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr(service, "_get_tokenizer", lambda: lambda text: text.split())
    monkeypatch.setattr(
        service,
        "_load_bm25_index",
        lambda path: _FakeBM25(scores=scores_by_name[path.name], calls=[]),
    )

    response = asyncio.run(_query(top_k=2, include_payloads=False, include_diagnostics=False))

    assert [hit["chunk_id"] for hit in response["results"][0]["bm25_hits"]] == ["a-chunk", "z-chunk"]


def test_metadata_pickle_is_not_deserialized_during_query_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores_by_name = {
        "shard_00": [3.0, 2.0],
        "shard_01": [9.0, 8.0],
        "shard_02": [1.0, 0.5],
    }
    payload_lookup = _FakePayloadLookup(calls=[])
    for name in scores_by_name:
        _write_shard(tmp_path, name, chunk_ids=_metadata(name, scores_by_name[name])["chunk_ids"])

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr(service, "_get_tokenizer", lambda: lambda text: text.split())
    monkeypatch.setattr(
        service,
        "_load_bm25_index",
        lambda path: _FakeBM25(scores=scores_by_name[path.name], calls=[]),
    )
    monkeypatch.setattr(service, "_load_metadata", lambda path: pytest.fail("metadata pickle must not be deserialized during queries"))
    monkeypatch.setattr(service, "_open_payload_lookup", lambda index_dir: payload_lookup)

    index = service._load_index()

    assert not any(hasattr(shard, "payloads") for shard in index.shards)
    assert [len(shard.chunk_ids) for shard in index.shards] == [2, 2, 2]

    response = asyncio.run(_query(top_k=2, include_payloads=True, include_diagnostics=True))

    assert payload_lookup.calls == [["shard_01-chunk-0", "shard_01-chunk-1"]]
    assert [hit["chunk_id"] for hit in response["results"][0]["bm25_hits"]] == [
        "shard_01-chunk-0",
        "shard_01-chunk-1",
    ]


def test_current_law_filter_uses_lazy_payload_lookup_after_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores_by_name = {
        "shard_00": [10.0, 9.0, 8.0],
        "shard_01": [7.0, 6.0, 5.0],
    }
    chunk_ids_by_name = {
        "shard_00": ["expired-top", "active-second", "future-third"],
        "shard_01": ["expired-fourth", "partial-fifth", "unknown-sixth"],
    }
    payload_lookup = _ValidityPayloadLookup(
        payloads={
            "expired-top": {"chunk_id": "expired-top", "validity_group": "expired", "chunk_text": "expired"},
            "active-second": {"chunk_id": "active-second", "validity_group": "active", "chunk_text": "active"},
            "future-third": {"chunk_id": "future-third", "validity_group": "future", "chunk_text": "future"},
            "expired-fourth": {"chunk_id": "expired-fourth", "validity_group": "expired", "chunk_text": "expired"},
            "partial-fifth": {"chunk_id": "partial-fifth", "validity_group": "partial", "chunk_text": "partial"},
            "unknown-sixth": {"chunk_id": "unknown-sixth", "validity_group": "unknown", "chunk_text": "unknown"},
        },
        calls=[],
    )
    for name in scores_by_name:
        _write_shard(tmp_path, name, chunk_ids=chunk_ids_by_name[name])

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setenv("BM25_FILTER_CANDIDATE_MIN", "1")
    monkeypatch.setenv("BM25_FILTER_CANDIDATE_MULTIPLIER", "3")
    monkeypatch.setattr(service, "_get_tokenizer", lambda: lambda text: text.split())
    monkeypatch.setattr(
        service,
        "_load_bm25_index",
        lambda path: _FakeBM25(scores=scores_by_name[path.name], calls=[]),
    )
    monkeypatch.setattr(service, "_load_metadata", lambda path: pytest.fail("metadata must not hydrate filters"))
    monkeypatch.setattr(service, "_open_payload_lookup", lambda index_dir: payload_lookup)

    response = asyncio.run(
        _query(
            top_k=3,
            include_payloads=True,
            include_diagnostics=True,
            filter_profile="current_law",
        )
    )

    hits = response["results"][0]["bm25_hits"]
    assert [hit["chunk_id"] for hit in hits] == ["active-second", "future-third", "partial-fifth"]
    assert [hit["bm25_score"] for hit in hits] == [9.0, 8.0, 6.0]
    assert response["diagnostics"]["filter_profile_used"] == "current_law"
    query_diagnostics = response["diagnostics"]["queries"][0]
    assert query_diagnostics["filter_profile_used"] == "current_law"
    assert query_diagnostics["pre_filter_candidate_count"] == 6
    assert query_diagnostics["post_filter_candidate_count"] == 3
    assert "expired-top" in payload_lookup.calls[0]


def test_chunk_id_map_can_be_generated_once_from_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scores_by_name = {"shard_00": [4.0, 3.0]}
    metadata_load_calls: list[str] = []
    _write_shard(tmp_path, "shard_00")

    def fake_load_metadata(path: Path):
        metadata_load_calls.append(path.name)
        return _metadata(path.name, scores_by_name[path.name])

    monkeypatch.setenv("BM25_INDEX_DIR", str(tmp_path))
    monkeypatch.setattr(service, "_get_tokenizer", lambda: lambda text: text.split())
    monkeypatch.setattr(service, "_load_bm25_index", lambda path: _FakeBM25(scores=scores_by_name[path.name], calls=[]))
    monkeypatch.setattr(service, "_load_metadata", fake_load_metadata)
    monkeypatch.setattr(service, "_open_payload_lookup", lambda index_dir: None)

    service._load_index()
    assert metadata_load_calls == ["shard_00"]
    assert (tmp_path / "shard_00" / "bm25_chunk_ids.jsonl").is_file()

    monkeypatch.setattr(service, "_load_metadata", lambda path: pytest.fail("query must reuse generated chunk-id map"))
    response = asyncio.run(_query(top_k=1, include_payloads=False, include_diagnostics=False))

    assert response["results"][0]["bm25_hits"][0]["chunk_id"] == "shard_00-chunk-0"


def test_auth_still_requires_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BM25_API_KEY", "secret")

    with pytest.raises(HTTPException) as exc_info:
        service._require_auth(_Request({"authorization": "Bearer wrong"}))

    assert exc_info.value.status_code == 401


async def _query(
    *,
    top_k: int,
    include_payloads: bool,
    include_diagnostics: bool,
    filter_profile: str = "broad",
) -> dict:
    return await service.bm25(
        {
            "input": {
                "queries": [{"qa_id": "q1", "question": "nghi hang nam"}],
                "bm25_top_k": top_k,
                "filter_profile": filter_profile,
                "include_payloads": include_payloads,
                "include_diagnostics": include_diagnostics,
            }
        },
        _Request(),
    )
