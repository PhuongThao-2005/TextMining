from __future__ import annotations

from retrieval.bm25_client import BM25Hit, BM25Result
from retrieval.bm25_retriever import BM25RemoteRetriever
from retrieval.stores import InMemoryVectorStore
from retrieval.schema import VectorRecord


class _Client:
    def search(self, queries, *, top_k: int, include_diagnostics: bool = False):
        return {
            "results": [
                BM25Result(
                    qa_id="q0",
                    bm25_hits=[
                        BM25Hit("chunk-2", 5.0, 1, 0),
                        BM25Hit("chunk-1", 3.0, 2, 0),
                    ],
                )
            ]
        }


def test_remote_bm25_hydrates_and_preserves_bm25_ranking() -> None:
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord("chunk-1", [], {"chunk_id": "chunk-1", "chunk_text": "first", "validity_group": "active"}),
            VectorRecord("chunk-2", [], {"chunk_id": "chunk-2", "chunk_text": "second", "validity_group": "active"}),
        ]
    )
    retriever = BM25RemoteRetriever(client=_Client(), payload_store=store, top_k=2, top_n=2)

    result = retriever.retrieve("query", filter_profile="broad")

    assert [chunk.chunk_id for chunk in result.chunks] == ["chunk-2", "chunk-1"]
    assert [chunk.vector_score for chunk in result.chunks] == [5.0, 3.0]
