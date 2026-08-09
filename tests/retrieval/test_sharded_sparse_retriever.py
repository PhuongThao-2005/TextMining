from pathlib import Path

import pytest

from retrieval.sparse_retriever import BM25SparseRetriever, ShardedBM25SparseRetriever
from retrieval.stores import SearchHit


class _FakeShard:
    def __init__(self, hits: list[SearchHit], total_documents: int) -> None:
        self.hits = hits
        self.total_documents = total_documents
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, top_k: int = 20) -> list[SearchHit]:
        self.calls.append((query, top_k))
        return self.hits[:top_k]


def _hit(chunk_id: str, score: float) -> SearchHit:
    return SearchHit(point_id=chunk_id, score=score, payload={"chunk_id": chunk_id})


def test_searches_every_shard_and_merges_global_top_k() -> None:
    first = _FakeShard([_hit("a", 4.0), _hit("duplicate", 2.0)], 2)
    second = _FakeShard([_hit("b", 5.0), _hit("duplicate", 3.0)], 2)
    retriever = ShardedBM25SparseRetriever(
        shards=[("shard_00", first), ("shard_01", second)]  # type: ignore[list-item]
    )

    hits = retriever.search("nhãn hiệu", top_k=3)

    assert [hit.point_id for hit in hits] == ["b", "a", "duplicate"]
    assert hits[-1].score == 3.0
    assert first.calls == [("nhãn hiệu", 3)]
    assert second.calls == [("nhãn hiệu", 3)]
    assert retriever.shard_count == 2
    assert retriever.total_documents == 4


def test_local_ids_that_restart_in_each_shard_do_not_collide() -> None:
    first = _FakeShard([SearchHit(point_id="0", score=2.0, payload={})], 1)
    second = _FakeShard([SearchHit(point_id="0", score=3.0, payload={})], 1)
    retriever = ShardedBM25SparseRetriever(
        shards=[("shard_00", first), ("shard_01", second)]  # type: ignore[list-item]
    )

    hits = retriever.search("lao động", top_k=2)

    assert [hit.point_id for hit in hits] == ["shard_01:0", "shard_00:0"]
    assert first.calls == [("lao động", 2)]
    assert second.calls == [("lao động", 2)]


def test_disk_backed_search_loads_shards_lazily_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("shard_00", "shard_01", "shard_02"):
        shard = tmp_path / name
        shard.mkdir()
        (shard / "bm25_index.pkl").write_bytes(b"index")
        (shard / "bm25_metadata.pkl").write_bytes(b"metadata")

    load_calls: list[str] = []

    class _Scores:
        def __init__(self, score: float) -> None:
            self.score = score

        def get_scores(self, _tokens: list[str]) -> list[float]:
            return [self.score]

    def fake_load(cls, shard_dir: Path) -> BM25SparseRetriever:
        load_calls.append(shard_dir.name)
        index = int(shard_dir.name.rsplit("_", 1)[1])
        return BM25SparseRetriever(
            bm25=_Scores(float(index + 1)),
            chunk_ids=[f"chunk-{index}"],
            payloads=[{"chunk_id": f"chunk-{index}"}],
            tokenizer=lambda value: value.split(),
        )

    monkeypatch.setattr(BM25SparseRetriever, "load", classmethod(fake_load))
    retriever = ShardedBM25SparseRetriever.load(tmp_path)

    assert load_calls == []
    hits = retriever.search("query", top_k=2)

    assert load_calls == ["shard_00", "shard_01", "shard_02"]
    assert [hit.point_id for hit in hits] == ["chunk-2", "chunk-1"]
    assert retriever.shard_count == 3


def test_discovers_complete_shards_and_rejects_partial_layout(tmp_path: Path) -> None:
    for name in ("shard_00", "shard_01"):
        shard = tmp_path / name
        shard.mkdir()
        (shard / "bm25_index.pkl").write_bytes(b"index")
        (shard / "bm25_metadata.pkl").write_bytes(b"metadata")

    assert [path.name for path in ShardedBM25SparseRetriever.discover_shard_dirs(tmp_path)] == [
        "shard_00",
        "shard_01",
    ]

    (tmp_path / "shard_01" / "bm25_metadata.pkl").unlink()
    with pytest.raises(FileNotFoundError, match="shard_01"):
        ShardedBM25SparseRetriever.discover_shard_dirs(tmp_path)
