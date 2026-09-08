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


def test_search_sends_filter_profile(monkeypatch) -> None:
    client = BM25Client(base_url="http://bm25.test", api_key="secret", max_retries=1)
    seen = {}

    def fake_request(method, path, payload):
        seen.update({"method": method, "path": path, "payload": payload})
        return {"index_version": "v1", "results": [{"qa_id": "q1", "bm25_hits": []}]}

    monkeypatch.setattr(client, "_request", fake_request)

    response = client.search(
        [{"qa_id": "q1", "question": "query"}],
        top_k=7,
        filter_profile="current_law",
        include_diagnostics=True,
        include_payloads=True,
    )

    assert response["results"][0].qa_id == "q1"
    assert seen["method"] == "POST"
    assert seen["path"] == "/bm25"
    assert seen["payload"]["input"] == {
        "queries": [{"qa_id": "q1", "question": "query"}],
        "bm25_top_k": 7,
        "filter_profile": "current_law",
        "include_diagnostics": True,
        "include_payloads": True,
    }
