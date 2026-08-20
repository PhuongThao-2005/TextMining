from __future__ import annotations

from types import SimpleNamespace

from retrieval.graph_rrf_retriever import GraphRRFGlobalReranker
from retrieval.schema import RetrievalResult, RetrievedChunk
from retrieval.stores import SearchHit


def _chunk(chunk_id: str, text: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        chunk_text=text,
        citation_anchor=chunk_id,
        citation_label=chunk_id,
        title="Fixture",
        article_number="1",
        unit_type="article",
        path=None,
        validity_group="active",
        legal_authority_rank=1,
        vector_score=score,
        rerank_score=score,
        id_str="doc-1",
        parent_unit_id="article-1",
        metadata={"chunk_id": chunk_id, "chunk_text": text},
    )


class _Store:
    def scroll(self, filters, limit):
        assert filters == {"chunk_id": {"in": ["c1", "c3"]}}
        assert limit == 2
        return [
            SearchHit("c1", 0.0, _chunk("c1", "dense and graph", 0.9).metadata),
            SearchHit("c3", 0.0, _chunk("c3", "graph only", 0.0).metadata),
        ]


class _DenseRetriever:
    store = _Store()

    def __init__(self):
        self.kwargs = None

    def retrieve(self, query, **kwargs):
        assert query == "legal question"
        self.kwargs = kwargs
        return RetrievalResult(
            chunks=[_chunk("c1", "dense and graph", 0.9), _chunk("c2", "dense only", 0.8)],
            total_candidates=2,
            filter_profile_used="broad",
        )


class _GraphExpansion:
    def expand(self, seed_ids, *, max_hop, max_context):
        assert seed_ids == ["c1", "c2"]
        assert (max_hop, max_context) == (2, 30)
        return SimpleNamespace(ordered_context_chunks=("c1", "c3"))


class _CrossEncoder:
    def __init__(self):
        self.pairs = None

    def predict(self, pairs):
        self.pairs = pairs
        scores = {"dense and graph": 0.5, "dense only": 0.1, "graph only": 0.9}
        return [scores[text] for _, text in pairs]


def test_dense_graph_rrf_global_reranker_pipeline_and_latency() -> None:
    dense = _DenseRetriever()
    cross_encoder = _CrossEncoder()
    retriever = GraphRRFGlobalReranker(
        dense_retriever=dense,
        graph_expansion=_GraphExpansion(),
        cross_encoder_name="fixture",
        cross_encoder=cross_encoder,
    )

    result, latency = retriever.retrieve_with_latency(
        "legal question", top_k=2, top_n=2, filter_profile="broad", score_threshold=0.3
    )

    assert dense.kwargs == {
        "filter_profile": "broad",
        "top_k": 2,
        "top_n": 2,
        "score_threshold": 0.3,
        "expand_units": False,
    }
    assert [chunk.chunk_id for chunk in result.chunks] == ["c3", "c1"]
    assert result.total_candidates == 3
    assert len(cross_encoder.pairs) == 3
    assert latency.dense_latency_s >= 0
    assert latency.graph_traversal_latency_s >= 0
    assert latency.fusion_latency_s >= 0
    assert latency.rerank_latency_s >= 0
    assert latency.total_latency_s >= 0
