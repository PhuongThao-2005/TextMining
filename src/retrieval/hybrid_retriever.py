"""Hybrid Retriever — Dense + Sparse fusion with RRF and Cross-Encoder reranking.

Combines ``VectorRetriever`` (Dense/FAISS) and ``BM25SparseRetriever`` (Sparse)
into a single retrieval pipeline with configurable fusion and reranking:

    1. **No rerank** (``Rerank-None-Hybrid``): merge Dense + Sparse by score, dedup
    2. **RRF** (``Rerank-RRF-Hybrid``): Reciprocal Rank Fusion
    3. **Cross-Encoder** (``Rerank-CrossEncoder-Hybrid``): CE rerank on merged candidates
    4. **RRF + Cross-Encoder** (``Rerank-RRFPlusCrossEncoder-Hybrid``): RRF first, CE on top

Usage::

    hybrid = HybridRetriever(
        dense_retriever=retriever,
        sparse_retriever=sparse,
        cross_encoder_name="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        use_rrf=True,
        use_cross_encoder=True,
    )
    result, latency = hybrid.retrieve_with_latency(query, top_k=30, top_n=10)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .retriever import VectorRetriever
from .schema import RetrievalResult, RetrievedChunk
from .sparse_retriever import BM25SparseRetriever
from .stores import SearchHit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LatencyBreakdown:
    """Latency measurements for each stage of the hybrid pipeline."""

    dense_latency_s: float = 0.0
    sparse_latency_s: float = 0.0
    fusion_latency_s: float = 0.0
    cross_encoder_latency_s: float = 0.0
    total_latency_s: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "dense_latency_s": round(self.dense_latency_s, 4),
            "sparse_latency_s": round(self.sparse_latency_s, 4),
            "fusion_latency_s": round(self.fusion_latency_s, 4),
            "cross_encoder_latency_s": round(self.cross_encoder_latency_s, 4),
            "total_latency_s": round(self.total_latency_s, 4),
        }


class HybridRetriever:
    """Hybrid Dense + Sparse retriever with optional RRF fusion and Cross-Encoder reranking.

    The five ablation configs map to constructor parameters as follows:

    +------------------------------------------+----------+--------+---------+---------------+
    | Config                                   | Dense    | Sparse | use_rrf | use_cross_enc |
    +==========================================+==========+========+=========+===============+
    | Retrieval-Hybrid-SparseDense             | ✓        | ✓      | False   | False         |
    +------------------------------------------+----------+--------+---------+---------------+
    | Rerank-None-Hybrid                       | ✓        | ✓      | False   | False         |
    +------------------------------------------+----------+--------+---------+---------------+
    | Rerank-RRF-Hybrid                        | ✓        | ✓      | True    | False         |
    +------------------------------------------+----------+--------+---------+---------------+
    | Rerank-CrossEncoder-Hybrid               | ✓        | ✓      | False   | True          |
    +------------------------------------------+----------+--------+---------+---------------+
    | Rerank-RRFPlusCrossEncoder-Hybrid        | ✓        | ✓      | True    | True          |
    +------------------------------------------+----------+--------+---------+---------------+
    """

    def __init__(
        self,
        *,
        dense_retriever: VectorRetriever,
        sparse_retriever: BM25SparseRetriever,
        cross_encoder_name: str | None = None,
        use_rrf: bool = False,
        use_cross_encoder: bool = False,
        rrf_k: int = 60,
    ) -> None:
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.use_rrf = use_rrf
        self.use_cross_encoder = use_cross_encoder
        self.rrf_k = rrf_k

        self._cross_encoder = None
        if use_cross_encoder:
            if cross_encoder_name is None:
                cross_encoder_name = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
            self._cross_encoder = self._load_cross_encoder(cross_encoder_name)
            self._cross_encoder_name = cross_encoder_name

    @staticmethod
    def _load_cross_encoder(model_name: str):
        """Lazily load a ``CrossEncoder`` from ``sentence-transformers``."""
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for Cross-Encoder reranking. "
                "Install it with: pip install sentence-transformers"
            ) from exc

        logger.info("Loading Cross-Encoder model: %s", model_name)
        return CrossEncoder(model_name)

    # ------------------------------------------------------------------
    # Dense search
    # ------------------------------------------------------------------

    def _dense_search(
        self,
        query: str,
        *,
        top_k: int,
        filter_profile: str = "broad",
        score_threshold: float | None = None,
    ) -> tuple[list[SearchHit], float]:
        """Run Dense retrieval via ``VectorRetriever``, return ``(hits, latency)``."""
        t0 = time.perf_counter()
        result = self.dense_retriever.retrieve(
            query,
            filter_profile=filter_profile,
            top_k=top_k,
            top_n=top_k,  # get all top_k, we fuse later
            score_threshold=score_threshold,
            expand_units=False,
        )
        latency = time.perf_counter() - t0

        # Convert RetrievedChunk back to SearchHit for uniform processing
        hits = [
            SearchHit(
                point_id=chunk.chunk_id,
                score=chunk.vector_score,
                payload=chunk.metadata,
            )
            for chunk in result.chunks
        ]
        return hits, latency

    # ------------------------------------------------------------------
    # Sparse search
    # ------------------------------------------------------------------

    def _sparse_search(
        self,
        query: str,
        *,
        top_k: int,
        filter_profile: str = "broad",
    ) -> tuple[list[SearchHit], float]:
        """Run Sparse (BM25) search, return ``(hits, latency)``."""
        hits, latency = self.sparse_retriever.search_with_latency(query, top_k=max(top_k * 3, top_k))
        allowed = {
            "current_law": {"active", "partial", "future"},
            "broad": {"active", "partial", "future", "expired", "unknown"},
            "historical": {"expired", "active", "partial"},
        }.get(filter_profile)
        if allowed is not None:
            hits = [
                hit for hit in hits
                if str(hit.payload.get("validity_group") or "unknown") in allowed
            ]
        return hits[:top_k], latency

    # ------------------------------------------------------------------
    # Fusion methods
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_by_score(
        dense_hits: list[SearchHit],
        sparse_hits: list[SearchHit],
    ) -> list[SearchHit]:
        """Simple score-based merge with dedup by chunk_id.

        Normalizes Dense (cosine 0–1) and Sparse (BM25 unbounded) scores to
        [0, 1] before combining. Keeps the highest combined score per chunk_id.
        """
        # Normalize scores
        dense_max = max((h.score for h in dense_hits), default=1.0) or 1.0
        sparse_max = max((h.score for h in sparse_hits), default=1.0) or 1.0

        combined: dict[str, SearchHit] = {}

        for hit in dense_hits:
            chunk_id = str(hit.payload.get("chunk_id") or hit.point_id)
            norm_score = hit.score / dense_max
            existing = combined.get(chunk_id)
            if existing is None or norm_score > existing.score:
                combined[chunk_id] = SearchHit(
                    point_id=hit.point_id,
                    score=norm_score,
                    payload=hit.payload,
                )

        for hit in sparse_hits:
            chunk_id = str(hit.payload.get("chunk_id") or hit.point_id)
            norm_score = hit.score / sparse_max
            existing = combined.get(chunk_id)
            if existing is None:
                combined[chunk_id] = SearchHit(
                    point_id=hit.point_id,
                    score=norm_score,
                    payload=hit.payload,
                )
            elif norm_score > existing.score:
                combined[chunk_id] = SearchHit(
                    point_id=hit.point_id,
                    score=norm_score,
                    payload=hit.payload,
                )

        return sorted(combined.values(), key=lambda h: h.score, reverse=True)

    @staticmethod
    def _rrf_fusion(
        dense_hits: list[SearchHit],
        sparse_hits: list[SearchHit],
        *,
        k: int = 60,
    ) -> list[SearchHit]:
        """Reciprocal Rank Fusion (RRF).

        ``score(d) = Σ_{r ∈ rankings} 1 / (k + rank_r(d))``

        where ``k`` is a smoothing constant (default 60, per original RRF paper).
        """
        rrf_scores: dict[str, float] = {}
        best_hit: dict[str, SearchHit] = {}

        for rank, hit in enumerate(dense_hits, start=1):
            chunk_id = str(hit.payload.get("chunk_id") or hit.point_id)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in best_hit:
                best_hit[chunk_id] = hit

        for rank, hit in enumerate(sparse_hits, start=1):
            chunk_id = str(hit.payload.get("chunk_id") or hit.point_id)
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in best_hit:
                best_hit[chunk_id] = hit

        # Build result sorted by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
        return [
            SearchHit(
                point_id=best_hit[cid].point_id,
                score=rrf_scores[cid],
                payload=best_hit[cid].payload,
            )
            for cid in sorted_ids
        ]

    # ------------------------------------------------------------------
    # Cross-Encoder reranking
    # ------------------------------------------------------------------

    def _cross_encoder_rerank(
        self,
        query: str,
        hits: list[SearchHit],
        *,
        top_n: int,
    ) -> tuple[list[SearchHit], float]:
        """Rerank hits using a Cross-Encoder model.

        Returns ``(reranked_hits[:top_n], latency_seconds)``.
        """
        if self._cross_encoder is None:
            raise RuntimeError("Cross-Encoder not loaded. Set use_cross_encoder=True.")

        if not hits:
            return [], 0.0

        t0 = time.perf_counter()

        # Build (query, passage) pairs
        pairs = []
        for hit in hits:
            text = str(hit.payload.get("chunk_text") or "")
            pairs.append((query, text))

        # Score with Cross-Encoder
        ce_scores = self._cross_encoder.predict(pairs)

        # Attach CE scores and sort
        scored = [
            SearchHit(
                point_id=hit.point_id,
                score=float(ce_score),
                payload=hit.payload,
            )
            for hit, ce_score in zip(hits, ce_scores)
        ]
        scored.sort(key=lambda h: h.score, reverse=True)

        latency = time.perf_counter() - t0
        return scored[:top_n], latency

    # ------------------------------------------------------------------
    # Main retrieve
    # ------------------------------------------------------------------

    def _to_retrieved_chunk(self, hit: SearchHit, rank: int) -> RetrievedChunk:
        """Convert a ``SearchHit`` to ``RetrievedChunk`` for output."""
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
            vector_score=float(hit.score),
            rerank_score=float(hit.score),
            id_str=str(payload.get("id_str") or ""),
            parent_unit_id=str(payload.get("parent_unit_id") or ""),
            metadata=payload,
        )

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 30,
        top_n: int = 10,
        filter_profile: str = "broad",
        score_threshold: float | None = None,
    ) -> RetrievalResult:
        """Run the full hybrid pipeline and return a ``RetrievalResult``."""
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
    ) -> tuple[RetrievalResult, LatencyBreakdown]:
        """Run the full hybrid pipeline, returning ``(RetrievalResult, LatencyBreakdown)``."""
        total_t0 = time.perf_counter()

        # Stage 1: Dense search
        dense_hits, dense_latency = self._dense_search(
            query,
            top_k=top_k,
            filter_profile=filter_profile,
            score_threshold=score_threshold,
        )

        # Stage 2: Sparse search
        sparse_hits, sparse_latency = self._sparse_search(
            query, top_k=top_k, filter_profile=filter_profile
        )

        # Stage 3: Fusion
        fusion_t0 = time.perf_counter()
        if self.use_rrf:
            fused_hits = self._rrf_fusion(dense_hits, sparse_hits, k=self.rrf_k)
        else:
            fused_hits = self._merge_by_score(dense_hits, sparse_hits)
        fusion_latency = time.perf_counter() - fusion_t0

        # Stage 4: Optional Cross-Encoder reranking
        ce_latency = 0.0
        if self.use_cross_encoder and self._cross_encoder is not None:
            # Feed fused candidates (more than top_n) to CE for reranking
            candidates = fused_hits[: top_n * 3]  # rerank top candidates
            fused_hits, ce_latency = self._cross_encoder_rerank(
                query, candidates, top_n=top_n
            )
        else:
            fused_hits = fused_hits[:top_n]

        total_latency = time.perf_counter() - total_t0

        # Convert to RetrievedChunk
        chunks = [
            self._to_retrieved_chunk(hit, rank)
            for rank, hit in enumerate(fused_hits, start=1)
        ]

        total_candidates = len(set(
            str(h.payload.get("chunk_id") or h.point_id) for h in dense_hits
        ) | set(
            str(h.payload.get("chunk_id") or h.point_id) for h in sparse_hits
        ))

        result = RetrievalResult(
            chunks=chunks,
            total_candidates=total_candidates,
            filter_profile_used=filter_profile,
            empty_filter_warning=False,
        )

        latency = LatencyBreakdown(
            dense_latency_s=dense_latency,
            sparse_latency_s=sparse_latency,
            fusion_latency_s=fusion_latency,
            cross_encoder_latency_s=ce_latency,
            total_latency_s=total_latency,
        )

        return result, latency
