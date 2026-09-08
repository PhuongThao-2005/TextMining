from __future__ import annotations

from retrieval.dense_client import DenseRemoteRetriever
from retrieval.schema import RetrievalResult, RetrievedChunk


class _Client:
    def search(self, query: str, **kwargs):
        assert query == "query"
        assert kwargs["top_k"] == 5
        assert kwargs["top_n"] == 2
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            chunk_text="text",
            citation_anchor="Article 1",
            citation_label="Citation",
            title="Law",
            article_number="1",
            unit_type="article",
            path="path",
            validity_group="active",
            legal_authority_rank=1,
            vector_score=0.8,
            rerank_score=0.9,
            id_str="doc-1",
            parent_unit_id="unit-1",
            metadata={"chunk_id": "chunk-1", "chunk_text": "text", "validity_group": "active"},
        )
        return RetrievalResult(
            chunks=[chunk],
            total_candidates=1,
            filter_profile_used="broad",
            latency_ms={"embedding": 1.0, "vector_search": 2.0, "payload_hydration": 3.0, "total": 10.0},
        )


def test_dense_remote_retriever_preserves_chunks_and_latency() -> None:
    retriever = DenseRemoteRetriever(client=_Client(), top_k=5, top_n=2)

    result, latency = retriever.retrieve_with_latency("query", filter_profile="broad")

    assert [chunk.chunk_id for chunk in result.chunks] == ["chunk-1"]
    assert latency.dense_latency_s == 0.01
    assert latency.embedding_latency_s == 0.001
