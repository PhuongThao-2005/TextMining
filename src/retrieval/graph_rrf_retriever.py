"""Dense retrieval with optional graph expansion, RRF, and global Cross-Encoder reranking."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Sequence

from knowledge_graph.expansion import GraphExpansion

from .retriever import VectorRetriever
from .schema import RetrievalResult, RetrievedChunk
from .stores import SearchHit


@dataclass(frozen=True)
class GraphRRFLatencyBreakdown:
    dense_latency_s: float = 0.0
    graph_traversal_latency_s: float = 0.0
    fusion_latency_s: float = 0.0
    rerank_latency_s: float = 0.0
    total_latency_s: float = 0.0


class GraphRRFGlobalReranker:
    """Fuse Dense and graph-derived rankings, then globally rerank candidates."""

    use_cross_encoder = True

    def __init__(
        self,
        *,
        dense_retriever: VectorRetriever,
        graph_expansion: GraphExpansion | None,
        cross_encoder_name: str | None = None,
        use_cross_encoder: bool = True,
        rrf_k: int = 60,
        graph_max_hop: int = 2,
        graph_max_context: int = 30,
        rerank_candidate_limit: int = 30,
        cross_encoder: Any | None = None,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1")
        if graph_max_hop < 1 or graph_max_context < 1 or rerank_candidate_limit < 1:
            raise ValueError("graph and reranker limits must be positive")
        self.dense_retriever = dense_retriever
        self.graph_expansion = graph_expansion
        self.use_cross_encoder = use_cross_encoder
        self.cross_encoder_name = cross_encoder_name or ""
        self.rrf_k = rrf_k
        self.graph_max_hop = graph_max_hop
        self.graph_max_context = graph_max_context
        self.rerank_candidate_limit = rerank_candidate_limit
        self._cross_encoder = (
            cross_encoder
            if cross_encoder is not None or not use_cross_encoder
            else self._load_cross_encoder(self.cross_encoder_name)
        )

    @staticmethod
    def _load_cross_encoder(model_name: str) -> Any:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for global Cross-Encoder reranking."
            ) from exc
        return CrossEncoder(model_name)

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
    ) -> tuple[RetrievalResult, GraphRRFLatencyBreakdown]:
        total_started = time.perf_counter()

        dense_started = time.perf_counter()
        dense_result = self.dense_retriever.retrieve(
            query,
            filter_profile=filter_profile,
            top_k=top_k,
            top_n=top_k,
            score_threshold=score_threshold,
            expand_units=False,
        )
        dense_latency = time.perf_counter() - dense_started

        graph_started = time.perf_counter()
        if self.graph_expansion is None:
            graph_chunks = []
        else:
            dense_ids = [chunk.chunk_id for chunk in dense_result.chunks]
            expansion = self.graph_expansion.expand(
                dense_ids,
                max_hop=self.graph_max_hop,
                max_context=self.graph_max_context,
            )
            graph_chunks = self._hydrate_graph_chunks(expansion.ordered_context_chunks)
        graph_latency = time.perf_counter() - graph_started

        fusion_started = time.perf_counter()
        fused = self._rrf_fuse(dense_result.chunks, graph_chunks) if graph_chunks else list(dense_result.chunks)
        fusion_latency = time.perf_counter() - fusion_started

        rerank_started = time.perf_counter()
        if self.use_cross_encoder:
            candidates = fused[: self.rerank_candidate_limit]
            reranked = self._global_rerank(query, candidates)[:top_n]
        else:
            reranked = fused[:top_n]
        rerank_latency = time.perf_counter() - rerank_started

        total_latency = time.perf_counter() - total_started
        result = RetrievalResult(
            chunks=reranked,
            total_candidates=len(fused),
            filter_profile_used=filter_profile,
            empty_filter_warning=dense_result.empty_filter_warning,
        )
        return result, GraphRRFLatencyBreakdown(
            dense_latency_s=dense_latency,
            graph_traversal_latency_s=graph_latency,
            fusion_latency_s=fusion_latency,
            rerank_latency_s=rerank_latency,
            total_latency_s=total_latency,
        )

    def _hydrate_graph_chunks(self, ordered_chunk_ids: Sequence[str]) -> list[RetrievedChunk]:
        ids = list(dict.fromkeys(str(value) for value in ordered_chunk_ids if value))
        if not ids:
            return []
        hits = self.dense_retriever.store.scroll(
            {"chunk_id": {"in": ids}},
            limit=len(ids),
        )
        by_id = {
            str(hit.payload.get("chunk_id") or hit.point_id): hit
            for hit in hits
        }
        return [
            self._chunk_from_hit(by_id[chunk_id], vector_score=0.0, rerank_score=0.0)
            for chunk_id in ids
            if chunk_id in by_id
        ]

    def _rrf_fuse(
        self,
        dense_chunks: Sequence[RetrievedChunk],
        graph_chunks: Sequence[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        scores: dict[str, float] = {}
        chunks: dict[str, RetrievedChunk] = {}
        for ranking in (dense_chunks, graph_chunks):
            for rank, chunk in enumerate(ranking, start=1):
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (self.rrf_k + rank)
                chunks.setdefault(chunk.chunk_id, chunk)
        ordered_ids = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
        return [self._copy_chunk(chunks[chunk_id], rerank_score=scores[chunk_id]) for chunk_id in ordered_ids]

    def _global_rerank(
        self, query: str, candidates: Sequence[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        pairs = [(query, chunk.chunk_text) for chunk in candidates]
        scores = self._cross_encoder.predict(pairs)
        if len(scores) != len(candidates):
            raise RuntimeError("Cross-Encoder returned an unexpected number of scores.")
        reranked = [
            self._copy_chunk(chunk, rerank_score=float(score))
            for chunk, score in zip(candidates, scores)
        ]
        return sorted(reranked, key=lambda chunk: (-chunk.rerank_score, chunk.chunk_id))

    @staticmethod
    def _copy_chunk(chunk: RetrievedChunk, *, rerank_score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk.chunk_id,
            chunk_text=chunk.chunk_text,
            citation_anchor=chunk.citation_anchor,
            citation_label=chunk.citation_label,
            title=chunk.title,
            article_number=chunk.article_number,
            unit_type=chunk.unit_type,
            path=chunk.path,
            validity_group=chunk.validity_group,
            legal_authority_rank=chunk.legal_authority_rank,
            vector_score=chunk.vector_score,
            rerank_score=rerank_score,
            id_str=chunk.id_str,
            parent_unit_id=chunk.parent_unit_id,
            metadata=chunk.metadata,
        )

    @staticmethod
    def _chunk_from_hit(
        hit: SearchHit, *, vector_score: float, rerank_score: float
    ) -> RetrievedChunk:
        payload = hit.payload
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
            vector_score=vector_score,
            rerank_score=rerank_score,
            id_str=str(payload.get("id_str") or ""),
            parent_unit_id=str(payload.get("parent_unit_id") or ""),
            metadata=payload,
        )
