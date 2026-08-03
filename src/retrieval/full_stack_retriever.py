"""Canonical Dense/Sparse/RRF/Cross-Encoder/Graph retrieval adapter.

This module composes the retrieval implementations owned by the retrieval and
knowledge-graph workstreams behind the single ``retrieve`` contract consumed by
the E2E runner.  Graph expansion is applied after hybrid fusion/reranking and is
bounded so it cannot silently flood the generator context.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from knowledge_graph.expansion import GraphExpansion

from .schema import RetrievalResult, RetrievedChunk


@dataclass(frozen=True)
class FullStackLatencyBreakdown:
    dense_latency_s: float = 0.0
    sparse_latency_s: float = 0.0
    graph_latency_s: float = 0.0
    fusion_latency_s: float = 0.0
    cross_encoder_latency_s: float = 0.0
    total_latency_s: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "dense_latency_s": self.dense_latency_s,
            "sparse_latency_s": self.sparse_latency_s,
            "graph_latency_s": self.graph_latency_s,
            "fusion_latency_s": self.fusion_latency_s,
            "cross_encoder_latency_s": self.cross_encoder_latency_s,
            "total_latency_s": self.total_latency_s,
        }


class FullStackRetriever:
    """Wrap a dense or hybrid retriever with bounded structural graph expansion."""

    def __init__(
        self,
        *,
        base_retriever: Any,
        dense_retriever: Any,
        graph_expansion: GraphExpansion | None = None,
        max_graph_seeds: int = 3,
        max_graph_hop: int = 1,
        max_graph_chunks: int = 10,
    ) -> None:
        if max_graph_seeds < 1 or max_graph_hop < 1 or max_graph_chunks < 0:
            raise ValueError("Graph bounds must use positive seeds/hops and non-negative chunks.")
        self.base_retriever = base_retriever
        self.dense_retriever = dense_retriever
        self.graph_expansion = graph_expansion
        self.max_graph_seeds = max_graph_seeds
        self.max_graph_hop = max_graph_hop
        self.max_graph_chunks = max_graph_chunks
        self.use_cross_encoder = bool(getattr(base_retriever, "use_cross_encoder", False))

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 30,
        top_n: int = 10,
        filter_profile: str = "broad",
        score_threshold: float | None = None,
    ) -> RetrievalResult:
        result, _ = self.retrieve_with_latency(
            query,
            top_k=top_k,
            top_n=top_n,
            filter_profile=filter_profile,
            score_threshold=score_threshold,
        )
        return result

    def retrieve_with_latency(
        self,
        query: str,
        *,
        top_k: int = 30,
        top_n: int = 10,
        filter_profile: str = "broad",
        score_threshold: float | None = None,
    ) -> tuple[RetrievalResult, FullStackLatencyBreakdown]:
        total_started = time.perf_counter()
        base_result, raw_latency = self._retrieve_base(
            query,
            top_k=top_k,
            top_n=top_n,
            filter_profile=filter_profile,
            score_threshold=score_threshold,
        )

        graph_latency = 0.0
        final_result = base_result
        if self.graph_expansion is not None and base_result.chunks and self.max_graph_chunks:
            graph_started = time.perf_counter()
            final_result = self._expand_graph(
                base_result,
                query=query,
                top_n=top_n,
                filter_profile=filter_profile,
            )
            graph_latency = time.perf_counter() - graph_started

        raw = vars(raw_latency) if hasattr(raw_latency, "__dict__") else raw_latency.to_dict()
        return final_result, FullStackLatencyBreakdown(
            dense_latency_s=float(raw.get("dense_latency_s") or 0.0),
            sparse_latency_s=float(raw.get("sparse_latency_s") or 0.0),
            graph_latency_s=graph_latency,
            fusion_latency_s=float(raw.get("fusion_latency_s") or 0.0),
            cross_encoder_latency_s=float(raw.get("cross_encoder_latency_s") or 0.0),
            total_latency_s=time.perf_counter() - total_started,
        )

    def _retrieve_base(self, query: str, **kwargs: Any) -> tuple[RetrievalResult, Any]:
        if hasattr(self.base_retriever, "retrieve_with_latency"):
            return self.base_retriever.retrieve_with_latency(query, **kwargs)

        started = time.perf_counter()
        result = self.base_retriever.retrieve(query, **kwargs)
        elapsed = time.perf_counter() - started
        return result, FullStackLatencyBreakdown(dense_latency_s=elapsed, total_latency_s=elapsed)

    def _expand_graph(
        self,
        result: RetrievalResult,
        *,
        query: str,
        top_n: int,
        filter_profile: str,
    ) -> RetrievalResult:
        seeds = list(result.chunks[: self.max_graph_seeds])
        seed_ids = {chunk.chunk_id for chunk in result.chunks}
        expanded_ids: list[str] = []
        for seed in seeds:
            expansion = self.graph_expansion.expand(
                [seed.chunk_id],
                max_hop=self.max_graph_hop,
                max_context=self.max_graph_chunks + 1,
            )
            for chunk_id in expansion.ordered_context_chunks:
                value = str(chunk_id)
                if value not in seed_ids and value not in expanded_ids:
                    expanded_ids.append(value)
                if len(expanded_ids) >= self.max_graph_chunks:
                    break
            if len(expanded_ids) >= self.max_graph_chunks:
                break

        if not expanded_ids:
            return result

        filters: dict[str, Any] = {"chunk_id": {"in": expanded_ids}}
        validity = {
            "current_law": ["active", "partial", "future"],
            "broad": ["active", "partial", "future", "expired", "unknown"],
            "historical": ["expired", "active", "partial"],
        }.get(filter_profile)
        if validity is not None:
            filters["validity_group"] = {"in": validity}

        store = self.dense_retriever.store
        hits = store.scroll(filters, limit=len(expanded_ids))
        by_id = {
            str(hit.payload.get("chunk_id") or hit.point_id): hit
            for hit in hits
        }
        graph_chunks = [
            self._to_chunk(by_id[chunk_id], query=query, filter_profile=filter_profile)
            for chunk_id in expanded_ids
            if chunk_id in by_id
        ]

        # Keep a majority of the relevance-ranked seeds and reserve bounded room
        # for structural evidence. Remaining retrieved chunks fill unused slots.
        seed_budget = min(len(result.chunks), max(1, (top_n + 1) // 2))
        ordered = [*result.chunks[:seed_budget], *graph_chunks, *result.chunks[seed_budget:]]
        deduped: list[RetrievedChunk] = []
        seen: set[str] = set()
        for chunk in ordered:
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            deduped.append(chunk)
            if len(deduped) >= top_n:
                break
        return RetrievalResult(
            chunks=deduped,
            total_candidates=result.total_candidates + len(graph_chunks),
            filter_profile_used=result.filter_profile_used,
            empty_filter_warning=result.empty_filter_warning,
        )

    @staticmethod
    def _to_chunk(hit: Any, *, query: str, filter_profile: str) -> RetrievedChunk:
        payload = hit.payload
        score = float(hit.score)
        return RetrievedChunk(
            chunk_id=str(payload.get("chunk_id") or hit.point_id),
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
            metadata={**payload, "retrieval_source": "graph", "query": query, "filter_profile": filter_profile},
        )
