from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from retrieval.hybrid_retriever import HybridRetriever
from retrieval.schema import RetrievalResult, RetrievedChunk
from retrieval.stores import SearchHit


def _payload(chunk_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "chunk_id": chunk_id,
        "chunk_text": f"text {chunk_id}",
        "citation_anchor": f"Article {chunk_id}",
        "citation_label": f"Citation {chunk_id}",
        "title": "Law",
        "article_number": "1",
        "unit_type": "article",
        "path": "Chapter / Article",
        "validity_group": "active",
        "legal_authority_rank": 1,
        "id_str": "doc",
        "parent_unit_id": "unit",
    }
    payload.update(overrides)
    return payload


def _chunk(chunk_id: str, score: float, *, metadata: dict[str, Any] | None = None) -> RetrievedChunk:
    payload = metadata or _payload(chunk_id)
    return RetrievedChunk(
        chunk_id=chunk_id,
        chunk_text=str(payload.get("chunk_text") or ""),
        citation_anchor=str(payload.get("citation_anchor") or ""),
        citation_label=str(payload.get("citation_label") or ""),
        title=str(payload.get("title") or ""),
        article_number=payload.get("article_number"),
        unit_type=str(payload.get("unit_type") or ""),
        path=payload.get("path"),
        validity_group=str(payload.get("validity_group") or "unknown"),
        legal_authority_rank=int(payload.get("legal_authority_rank") or 99),
        vector_score=score,
        rerank_score=score,
        id_str=str(payload.get("id_str") or ""),
        parent_unit_id=str(payload.get("parent_unit_id") or ""),
        metadata=payload,
    )


@dataclass
class _Dense:
    chunks: list[RetrievedChunk]
    delay: float = 0.0

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.store = None

    def retrieve(
        self,
        query: str,
        *,
        filter_profile: str,
        top_k: int,
        top_n: int,
        score_threshold: float | None,
        expand_units: bool,
    ) -> RetrievalResult:
        self.calls.append(
            {
                "query": query,
                "filter_profile": filter_profile,
                "top_k": top_k,
                "top_n": top_n,
                "score_threshold": score_threshold,
                "expand_units": expand_units,
            }
        )
        if self.delay:
            time.sleep(self.delay)
        return RetrievalResult(self.chunks[:top_n], len(self.chunks), filter_profile)


@dataclass
class _Sparse:
    hits: list[SearchHit]
    delay: float = 0.0

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def search_with_latency(
        self,
        query: str,
        *,
        top_k: int,
        filter_profile: str,
    ) -> tuple[list[SearchHit], float]:
        self.calls.append({"query": query, "top_k": top_k, "filter_profile": filter_profile})
        started = time.perf_counter()
        if self.delay:
            time.sleep(self.delay)
        return self.hits[:top_k], time.perf_counter() - started


def test_hybrid_runs_dense_and_bm25_concurrently_and_propagates_current_law() -> None:
    dense = _Dense([_chunk("dense-1", 0.9)], delay=0.18)
    sparse = _Sparse([SearchHit("bm25-1", 5.0, _payload("bm25-1"))], delay=0.18)
    retriever = HybridRetriever(dense_retriever=dense, sparse_retriever=sparse, use_rrf=True)

    started = time.perf_counter()
    result, latency = retriever.retrieve_with_latency(
        "question",
        top_k=3,
        top_n=2,
        filter_profile="current_law",
        score_threshold=0.2,
    )
    wall = time.perf_counter() - started

    assert [chunk.chunk_id for chunk in result.chunks] == ["dense-1", "bm25-1"]
    assert dense.calls == [
        {
            "query": "question",
            "filter_profile": "current_law",
            "top_k": 3,
            "top_n": 3,
            "score_threshold": 0.2,
            "expand_units": False,
        }
    ]
    assert sparse.calls == [{"query": "question", "top_k": 3, "filter_profile": "current_law"}]
    assert wall < 0.32
    assert latency.total_latency_s < 0.32


def test_weighted_rrf_uses_equal_weights_like_legacy_rrf() -> None:
    dense = [SearchHit("d1", 0.9, _payload("d1")), SearchHit("shared", 0.8, _payload("shared"))]
    sparse = [SearchHit("s1", 5.0, _payload("s1")), SearchHit("shared", 4.0, _payload("shared"))]

    legacy = HybridRetriever._rrf_fusion(dense, sparse, k=60)
    explicit_equal = HybridRetriever._rrf_fusion(
        dense,
        sparse,
        k=60,
        dense_weight=1.0,
        bm25_weight=1.0,
    )

    assert [(hit.point_id, hit.score) for hit in explicit_equal] == [
        (hit.point_id, hit.score) for hit in legacy
    ]
    assert explicit_equal[0].point_id == "shared"


def test_weighted_rrf_can_downweight_bm25_without_changing_branch_ranking() -> None:
    dense = [SearchHit("dense-1", 0.9, _payload("dense-1"))]
    sparse = [SearchHit("bm25-1", 99.0, _payload("bm25-1"))]

    fused = HybridRetriever._rrf_fusion(
        dense,
        sparse,
        k=60,
        dense_weight=1.0,
        bm25_weight=0.3,
    )

    assert [hit.point_id for hit in fused] == ["dense-1", "bm25-1"]


def test_duplicate_rrf_hit_preserves_full_citation_metadata() -> None:
    dense_payload = {"chunk_id": "shared"}
    bm25_payload = _payload("shared", citation_anchor="Article 9", chunk_text="full legal text")
    dense = [SearchHit("shared", 0.9, dense_payload)]
    sparse = [SearchHit("shared", 5.0, bm25_payload)]
    retriever = HybridRetriever(
        dense_retriever=_Dense([]),
        sparse_retriever=_Sparse([]),
        use_rrf=True,
    )

    fused = HybridRetriever._rrf_fusion(dense, sparse, k=60)
    chunk = retriever._to_retrieved_chunk(fused[0], 1)

    assert chunk.chunk_id == "shared"
    assert chunk.chunk_text == "full legal text"
    assert chunk.citation_anchor == "Article 9"
    assert chunk.citation_label == "Citation shared"
