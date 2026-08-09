from __future__ import annotations

from dataclasses import dataclass

from retrieval.full_stack_retriever import FullStackLatencyBreakdown, FullStackRetriever
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.schema import RetrievalResult, RetrievedChunk
from retrieval.stores import SearchHit


def _chunk(chunk_id: str, score: float = 1.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        chunk_text=f"text {chunk_id}",
        citation_anchor=chunk_id,
        citation_label=chunk_id,
        title="Fixture",
        article_number=None,
        unit_type="chunk",
        path=None,
        validity_group="active",
        legal_authority_rank=1,
        vector_score=score,
        rerank_score=score,
        id_str="doc-1",
        parent_unit_id="p-1",
        metadata={"chunk_id": chunk_id},
    )


class _Base:
    use_cross_encoder = True

    def retrieve_with_latency(self, query: str, **kwargs):
        del query, kwargs
        result = RetrievalResult([_chunk("s1"), _chunk("s2", .9), _chunk("s3", .8)], 3, "broad")
        latency = FullStackLatencyBreakdown(
            dense_latency_s=.1,
            sparse_latency_s=.2,
            fusion_latency_s=.3,
            cross_encoder_latency_s=.4,
        )
        return result, latency


class _Expansion:
    def expand(self, seed_ids, **kwargs):
        del kwargs
        seed = seed_ids[0]
        ids = (seed, "g1") if seed == "s1" else (seed, "g2")
        return type("Expansion", (), {"ordered_context_chunks": ids})()


class _Store:
    def scroll(self, filters, limit):
        wanted = filters["chunk_id"]["in"]
        payloads = {
            value: {
                "chunk_id": value,
                "chunk_text": f"graph {value}",
                "validity_group": "active",
                "id_str": "doc-1",
                "parent_unit_id": "p-1",
            }
            for value in wanted
        }
        return [SearchHit(value, 0.0, payloads[value]) for value in wanted[:limit]]


@dataclass
class _Dense:
    store: _Store


def test_full_stack_reserves_context_for_bounded_graph_evidence() -> None:
    retriever = FullStackRetriever(
        base_retriever=_Base(),
        dense_retriever=_Dense(_Store()),
        graph_expansion=_Expansion(),
        max_graph_seeds=2,
        max_graph_hop=1,
        max_graph_chunks=2,
    )
    result, latency = retriever.retrieve_with_latency("query", top_k=12, top_n=4, filter_profile="broad")
    assert [chunk.chunk_id for chunk in result.chunks] == ["s1", "s2", "g1", "g2"]
    assert result.total_candidates == 5
    assert latency.dense_latency_s == .1
    assert latency.sparse_latency_s == .2
    assert latency.fusion_latency_s == .3
    assert latency.cross_encoder_latency_s == .4
    assert latency.graph_latency_s >= 0
    assert retriever.use_cross_encoder is True


def test_full_stack_without_graph_preserves_base_result() -> None:
    retriever = FullStackRetriever(
        base_retriever=_Base(),
        dense_retriever=_Dense(_Store()),
        graph_expansion=None,
    )
    result = retriever.retrieve("query", top_n=3)
    assert [chunk.chunk_id for chunk in result.chunks] == ["s1", "s2", "s3"]


def test_sparse_candidates_honor_the_shared_filter_profile() -> None:
    class Sparse:
        def search_with_latency(self, query, top_k):
            del query, top_k
            return (
                [
                    SearchHit("active", 2.0, {"chunk_id": "active", "validity_group": "active"}),
                    SearchHit("expired", 1.0, {"chunk_id": "expired", "validity_group": "expired"}),
                ],
                0.01,
            )

    hybrid = HybridRetriever.__new__(HybridRetriever)
    hybrid.sparse_retriever = Sparse()
    current, _ = hybrid._sparse_search("q", top_k=5, filter_profile="current_law")
    assert [hit.point_id for hit in current] == ["active"]
    broad, _ = hybrid._sparse_search("q", top_k=5, filter_profile="broad")
    assert [hit.point_id for hit in broad] == ["active", "expired"]


def test_cross_encoder_passage_includes_legal_identity_metadata() -> None:
    passage = HybridRetriever._rerank_passage(
        {
            "citation_anchor": "Nghị định 204/2004/NĐ-CP, Điều 1",
            "title": "Chế độ tiền lương",
            "so_ky_hieu": "204/2004/NĐ-CP",
            "path": "Điều 1",
            "chunk_text": "Nội dung quy định.",
        }
    )

    assert "Nghị định 204/2004/NĐ-CP" in passage
    assert "Chế độ tiền lương" in passage
    assert "204/2004/NĐ-CP" in passage
    assert "Điều 1" in passage
    assert passage.endswith("Nội dung quy định.")


def test_cross_encoder_passage_deduplicates_identical_metadata() -> None:
    passage = HybridRetriever._rerank_passage(
        {"citation_anchor": "Điều 1", "path": "Điều 1", "chunk_text": "Nội dung"}
    )

    assert passage.splitlines() == ["Điều 1", "Nội dung"]
