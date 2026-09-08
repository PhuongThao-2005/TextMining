from __future__ import annotations

from retrieval.bm25_client import BM25Client


def test_parse_result_accepts_sharded_hits_without_local_index() -> None:
    result = BM25Client._parse_result(
        {
            "qa_id": "q1",
            "bm25_hits": [
                {
                    "chunk_id": "chunk-1",
                    "bm25_score": 4.5,
                    "rank": 1,
                    "shard_id": 7,
                    "shard_name": "shard_07",
                    "shard_rank": "2",
                    "payload": {"chunk_id": "chunk-1", "chunk_text": "text"},
                }
            ],
        }
    )

    hit = result.bm25_hits[0]
    assert hit.chunk_id == "chunk-1"
    assert hit.local_index is None
    assert hit.shard_id == 7
    assert hit.shard_name == "shard_07"
    assert hit.shard_rank == 2
    assert hit.payload["chunk_text"] == "text"
