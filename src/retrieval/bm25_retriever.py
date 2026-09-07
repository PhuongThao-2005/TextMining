from __future__ import annotations

import time
from typing import Any

from knowledge_graph.context_schema import GraphGuidedFilter

from .bm25_client import BM25Client
from .schema import RetrievalResult, RetrievedChunk, VALID_FILTER_PROFILES
from .stores import SearchHit, VectorStore, payload_matches


class BM25RemoteRetriever:
    """Remote BM25 retrieval flow that returns the shared RetrievalResult shape."""

    def __init__(
        self,
        *,
        client: BM25Client,
        payload_store: VectorStore,
        top_k: int = 30,
        top_n: int = 10,
    ) -> None:
        self.client = client
        self.payload_store = payload_store
        self.top_k = top_k
        self.top_n = top_n

    def retrieve(
        self,
        query: str,
        filter_profile: str = "current_law",
        id_str_filter: list[str] | None = None,
        graph_guided_filter: GraphGuidedFilter | None = None,
        top_k: int | None = None,
        top_n: int | None = None,
        score_threshold: float | None = None,
        expand_units: bool | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        if filter_profile not in VALID_FILTER_PROFILES:
            raise ValueError(f"Unknown filter_profile={filter_profile!r}")
        if graph_guided_filter is not None:
            id_str_filter = list(graph_guided_filter.id_strs)
            filter_profile = "graph_guided"
            if graph_guided_filter.empty_filter_warning:
                return RetrievalResult([], 0, filter_profile, empty_filter_warning=True)
        if filter_profile == "graph_guided" and not id_str_filter:
            return RetrievalResult([], 0, filter_profile, empty_filter_warning=True)

        top_k = top_k or self.top_k
        top_n = top_n or self.top_n
        filters = self._build_filters(filter_profile, id_str_filter, extra_filters)
        response = self.client.search(
            [{"qa_id": "q0", "question": query}],
            top_k=max(top_k, top_n),
        )
        bm25_result = response["results"][0]
        hits_by_id = {hit.chunk_id: hit for hit in bm25_result.bm25_hits}
        if not hits_by_id:
            return RetrievalResult([], 0, filter_profile, empty_filter_warning=False)

        search_hits = self.payload_store.scroll({"chunk_id": {"in": list(hits_by_id)}}, limit=len(hits_by_id))

        chunks: list[RetrievedChunk] = []
        for hit in search_hits:
            bm25_hit = hits_by_id.get(str(hit.payload.get("chunk_id") or hit.point_id))
            if bm25_hit is None:
                continue
            if filters and not payload_matches(hit.payload, filters):
                continue
            if score_threshold is not None and bm25_hit.bm25_score < score_threshold:
                continue
            chunks.append(self._to_retrieved_chunk(hit, bm25_hit.bm25_score))

        chunks.sort(key=lambda chunk: chunk.vector_score, reverse=True)
        return RetrievalResult(chunks[:top_n], len(chunks), filter_profile, empty_filter_warning=False)

    def search_with_latency(self, query: str, *, top_k: int = 20) -> tuple[list[SearchHit], float]:
        started = time.perf_counter()
        result = self.retrieve(query, filter_profile="broad", top_k=top_k, top_n=top_k)
        latency = time.perf_counter() - started
        hits = [
            SearchHit(
                point_id=chunk.chunk_id,
                score=chunk.vector_score,
                payload=chunk.metadata,
            )
            for chunk in result.chunks
        ]
        return hits, latency

    def _build_filters(
        self,
        filter_profile: str,
        id_str_filter: list[str] | None,
        extra_filters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if filter_profile == "current_law":
            filters["validity_group"] = {"in": ["active", "partial", "future"]}
        elif filter_profile == "broad":
            filters["validity_group"] = {"in": ["active", "partial", "future", "expired", "unknown"]}
        elif filter_profile == "historical":
            filters["validity_group"] = {"in": ["expired", "active", "partial"]}
        elif filter_profile == "graph_guided":
            filters["id_str"] = {"in": list(id_str_filter or [])}

        if extra_filters:
            filters.update(extra_filters)
        return filters

    @staticmethod
    def _to_retrieved_chunk(hit: SearchHit, score: float) -> RetrievedChunk:
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
            vector_score=float(score),
            rerank_score=float(score),
            id_str=str(payload.get("id_str") or ""),
            parent_unit_id=str(payload.get("parent_unit_id") or ""),
            metadata=payload,
        )
