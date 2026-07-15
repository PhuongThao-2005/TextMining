from __future__ import annotations

from typing import Any

from knowledge_graph.context_schema import GraphGuidedFilter
from knowledge_graph.expansion import GraphExpansion

from .config import VectorIndexConfig
from .embeddings import Embedder
from .io_utils import clean_text
from .schema import RetrievalResult, RetrievedChunk, VALID_FILTER_PROFILES
from .stores import SearchHit, VectorStore


class VectorRetriever:
    """Baseline vector retrieval flow: query embed -> filter -> expand -> rerank."""

    def __init__(
        self,
        *,
        config: VectorIndexConfig,
        embedder: Embedder,
        store: VectorStore,
        graph_expansion: GraphExpansion | None = None,
    ) -> None:
        self.config = config
        self.embedder = embedder
        self.store = store
        self.graph_expansion = graph_expansion

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

        top_k = top_k or self.config.top_k
        top_n = top_n or self.config.top_n
        score_threshold = self.config.score_threshold if score_threshold is None else score_threshold
        expand_units = self.config.expand_units if expand_units is None else expand_units
        query_vector = self.embedder.encode_queries([clean_text(query)])[0]
        filters = self._build_filters(filter_profile, id_str_filter, extra_filters)
        hits = self.store.search(query_vector, limit=top_k, score_threshold=score_threshold, filters=filters)
        total_candidates = len(hits)

        if expand_units and hits:
            hits = self._expand_same_units(hits)

        ranked = sorted(
            (self._to_retrieved_chunk(hit, query, filter_profile) for hit in self._dedupe(hits)),
            key=lambda chunk: chunk.rerank_score,
            reverse=True,
        )
        return RetrievalResult(ranked[:top_n], total_candidates, filter_profile, empty_filter_warning=False)

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

    def _expand_same_units(self, hits: list[SearchHit]) -> list[SearchHit]:
        if self.graph_expansion is None:
            return self._expand_same_units_local(hits)

        ordered_chunk_ids: list[str] = []
        for hit in hits:
            chunk_id = str(hit.payload.get("chunk_id") or hit.point_id)
            expanded = self.graph_expansion.expand(
                [chunk_id],
                max_hop=1,
                max_context=(self.config.max_expansion_chunks * 2) + 1,
            )
            ordered_chunk_ids.extend(expanded.ordered_context_chunks)
        if not ordered_chunk_ids:
            return list(hits)

        sibling_hits = self.store.scroll({"chunk_id": {"in": self._dedupe_chunk_ids(ordered_chunk_ids)}}, limit=len(ordered_chunk_ids))
        return list(hits) + sibling_hits

    def _expand_same_units_local(self, hits: list[SearchHit]) -> list[SearchHit]:
        """Fetch same-provision neighbors without one full payload scan per hit.

        Groups seed hits by ``parent_unit_id`` and issues one ``scroll`` per unit
        over the union of needed ``chunk_index_in_unit`` windows. On the SQLite
        store this becomes a single indexed query per parent instead of N full
        table scans.
        """
        expanded = list(hits)
        parent_ranges: dict[str, tuple[int, int]] = {}
        for hit in hits:
            payload = hit.payload
            parent_unit_id = payload.get("parent_unit_id")
            index = payload.get("chunk_index_in_unit")
            if not parent_unit_id or not isinstance(index, int):
                continue
            low = max(1, index - self.config.max_expansion_chunks)
            high = index + self.config.max_expansion_chunks
            current = parent_ranges.get(str(parent_unit_id))
            if current is None:
                parent_ranges[str(parent_unit_id)] = (low, high)
            else:
                parent_ranges[str(parent_unit_id)] = (
                    min(current[0], low),
                    max(current[1], high),
                )

        for parent_unit_id, (low, high) in parent_ranges.items():
            # Bound the fetch; each unit window is tiny relative to the corpus.
            limit = max((high - low + 1) * 4, (self.config.max_expansion_chunks * 2) + 1)
            siblings = self.store.scroll(
                {
                    "parent_unit_id": parent_unit_id,
                    "chunk_index_in_unit": {"range": (low, high)},
                },
                limit=limit,
            )
            expanded.extend(siblings)
        return expanded

    @staticmethod
    def _dedupe_chunk_ids(chunk_ids: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for chunk_id in chunk_ids:
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            deduped.append(chunk_id)
        return deduped

    @staticmethod
    def _dedupe(hits: list[SearchHit]) -> list[SearchHit]:
        # Phase 1: dedupe by chunk_id (keep highest score per ID)
        best_by_id: dict[str, SearchHit] = {}
        for hit in hits:
            chunk_id = str(hit.payload.get("chunk_id") or hit.point_id)
            current = best_by_id.get(chunk_id)
            if current is None or hit.score > current.score:
                best_by_id[chunk_id] = hit

        # Phase 2: dedupe by chunk_text content (keep highest score per text)
        # Handles structuring duplicates: different chunk_ids, identical text
        best_by_text: dict[str, SearchHit] = {}
        for hit in best_by_id.values():
            text = hit.payload.get("chunk_text", "")
            current = best_by_text.get(text)
            if current is None or hit.score > current.score:
                best_by_text[text] = hit

        return list(best_by_text.values())

    def _to_retrieved_chunk(self, hit: SearchHit, query: str, filter_profile: str) -> RetrievedChunk:
        payload = hit.payload
        rerank_score = self._rerank_score(hit.score, payload, query, filter_profile)
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
            rerank_score=rerank_score,
            id_str=str(payload.get("id_str") or ""),
            parent_unit_id=str(payload.get("parent_unit_id") or ""),
            metadata=payload,
        )

    @staticmethod
    def _rerank_score(score: float, payload: dict[str, Any], query: str, filter_profile: str) -> float:
        out = float(score)
        rank = int(payload.get("legal_authority_rank") or 99)
        validity = payload.get("validity_group")
        if rank <= 2:
            out += 0.10
        if validity == "active":
            out += 0.08
        if payload.get("unit_type") == "article":
            out += 0.05
        query_norm = clean_text(query).lower()
        title = clean_text(payload.get("title")).lower()
        citation = clean_text(payload.get("citation_label")).lower()
        if (title and title in query_norm) or (citation and citation in query_norm):
            out += 0.10
        if rank >= 7 or rank == 99:
            out -= 0.05
        if validity == "expired" and filter_profile != "historical":
            out -= 0.08
        if validity == "unknown":
            out -= 0.03
        if payload.get("quality_flags"):
            out -= 0.05
        if payload.get("structuring_quality_flags"):
            out -= 0.02
        return out
