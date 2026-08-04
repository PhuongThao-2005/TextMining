from pathlib import Path

import pytest

from retrieval.sparse_retriever import ShardedBM25SparseRetriever
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
