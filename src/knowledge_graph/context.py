from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from retrieval.io_utils import clean_text

from .builder import KnowledgeGraph
from .context_schema import EvidenceContext, GraphGuidedFilter
from .overlay_schema import DocumentOverlay
from .traversal import TraversalResult


FilterProfile = Literal["current_law", "broad", "historical", "graph_guided"]


@dataclass(frozen=True)
class QueryConstraints:
    """Optional non-graph constraints applied during context construction."""

    legal_authority_rank_max: int | None = None
    legal_authority_rank_min: int | None = None
    validity_groups: tuple[str, ...] = ()
    issuing_authority_codes: tuple[str, ...] = ()
    legal_field_codes: tuple[str, ...] = ()
    sector_codes: tuple[str, ...] = ()
    scope_codes: tuple[str, ...] = ()
    loai_van_ban: tuple[str, ...] = ()
    issue_year_min: int | None = None
    issue_year_max: int | None = None


class ContextBuilder:
    """Build graph-guided filters and evidence bundles from traversal output.

    This service only prepares structured context for retrieval. It does not
    query the vector store, embed text, or mutate graph nodes.
    """

    def build_graph_guided_filter(
        self,
        *,
        graph: KnowledgeGraph,
        traversal: TraversalResult,
        overlays: dict[str, DocumentOverlay],
        filter_profile: FilterProfile = "current_law",
        constraints: QueryConstraints | None = None,
    ) -> GraphGuidedFilter:
        """Build a hard `id_str` filter from graph traversal plus overlays."""

        constraints = constraints or QueryConstraints()
        candidate_ids = self._candidate_ids_for_profile(graph, traversal, overlays, filter_profile)
        filtered_ids = self._apply_constraints(graph, overlays, candidate_ids, constraints)
        if not filtered_ids:
            return GraphGuidedFilter(id_strs=(), empty_filter_warning=True, filter_profile=filter_profile, reason="No documents matched the graph-guided filter.")
        return GraphGuidedFilter(id_strs=tuple(filtered_ids), empty_filter_warning=False, filter_profile=filter_profile)

    def build_evidence_context(
        self,
        *,
        graph: KnowledgeGraph,
        traversal: TraversalResult,
        overlays: dict[str, DocumentOverlay],
        filter_profile: FilterProfile = "current_law",
        constraints: QueryConstraints | None = None,
    ) -> EvidenceContext:
        """Build a retrieval-ready evidence bundle from graph results."""

        graph_filter = self.build_graph_guided_filter(
            graph=graph,
            traversal=traversal,
            overlays=overlays,
            filter_profile=filter_profile,
            constraints=constraints,
        )
        doc_ids = graph_filter.id_strs
        filtered_overlays = tuple(overlays[id_str] for id_str in doc_ids if id_str in overlays)
        return EvidenceContext(
            filter=graph_filter,
            traversal=traversal,
            paths=traversal.paths,
            documents=doc_ids,
            overlays=filtered_overlays,
            warnings=(graph_filter.reason,) if graph_filter.empty_filter_warning and graph_filter.reason else (),
        )

    def build_citation_context(
        self,
        *,
        graph: KnowledgeGraph,
        traversal: TraversalResult,
        overlays: dict[str, DocumentOverlay],
        filter_profile: FilterProfile = "current_law",
        constraints: QueryConstraints | None = None,
    ) -> tuple[str, ...]:
        """Return document IDs suitable for citation display and downstream joins."""

        return self.build_graph_guided_filter(
            graph=graph,
            traversal=traversal,
            overlays=overlays,
            filter_profile=filter_profile,
            constraints=constraints,
        ).id_strs

    def build_empty_response(
        self,
        *,
        filter_profile: FilterProfile,
        reason: str,
    ) -> GraphGuidedFilter:
        """Construct an explicit empty-filter result."""

        return GraphGuidedFilter(id_strs=(), empty_filter_warning=True, filter_profile=filter_profile, reason=reason)

    def _candidate_ids_for_profile(
        self,
        graph: KnowledgeGraph,
        traversal: TraversalResult,
        overlays: dict[str, DocumentOverlay],
        filter_profile: FilterProfile,
    ) -> list[str]:
        """Compute the candidate `id_str` set for the requested filter profile."""

        traversal_ids = [candidate for candidate in traversal.visited_ids if candidate in graph.documents]
        if filter_profile == "graph_guided":
            return traversal_ids

        allowed_statuses = {
            "current_law": {"active", "partial", "future"},
            "broad": {"active", "partial", "future", "expired", "unknown", "suspended"},
            "historical": {"expired", "active", "partial", "suspended"},
        }[filter_profile]
        return [
            id_str
            for id_str in traversal_ids
            if overlays.get(id_str) is None or clean_text(overlays[id_str].currency_status).lower() in allowed_statuses
        ]

    def _apply_constraints(
        self,
        graph: KnowledgeGraph,
        overlays: dict[str, DocumentOverlay],
        candidate_ids: Iterable[str],
        constraints: QueryConstraints,
    ) -> list[str]:
        """Apply graph-visible and overlay-derived constraints to candidate documents."""

        filtered: list[str] = []
        for id_str in candidate_ids:
            document = graph.documents.get(id_str)
            if document is None:
                continue
            overlay = overlays.get(id_str)
            if constraints.legal_authority_rank_max is not None and overlay is not None and overlay.legal_authority_rank > constraints.legal_authority_rank_max:
                continue
            if constraints.legal_authority_rank_min is not None and overlay is not None and overlay.legal_authority_rank < constraints.legal_authority_rank_min:
                continue
            if constraints.validity_groups:
                status = clean_text(overlay.currency_status).lower() if overlay is not None else "unknown"
                if status not in {clean_text(item).lower() for item in constraints.validity_groups}:
                    continue
            if constraints.issuing_authority_codes and document.issuing_authority.code not in constraints.issuing_authority_codes:
                continue
            if constraints.legal_field_codes and document.legal_field.code not in constraints.legal_field_codes:
                continue
            if constraints.sector_codes and document.sector.code not in constraints.sector_codes:
                continue
            if constraints.scope_codes and document.scope.code not in constraints.scope_codes:
                continue
            if constraints.loai_van_ban and document.loai_van_ban not in constraints.loai_van_ban:
                continue
            if constraints.issue_year_min is not None and (document.issue_year is None or document.issue_year < constraints.issue_year_min):
                continue
            if constraints.issue_year_max is not None and (document.issue_year is None or document.issue_year > constraints.issue_year_max):
                continue
            filtered.append(id_str)
        return filtered
