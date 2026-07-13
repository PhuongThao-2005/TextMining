from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .builder import GraphBuildResult, GraphBuilder, KnowledgeGraph
from .context import ContextBuilder, FilterProfile, QueryConstraints
from .context_schema import EvidenceContext, GraphGuidedFilter
from .edge_parser import parse_edge_rows
from .edge_schema import GraphEdge
from .loader import GraphLoader, GraphLoaderPaths, GraphSourceBundle
from .overlay import OverlayBundle, OverlayJoiner
from .overlay_schema import AuthorityIndexEntry, DocumentOverlay, ValidityEvent
from .parser import (
    ChunkNode,
    DocumentNode,
    ExternalStubNode,
    ProvisionNode,
    TextProvenanceRecord,
    index_text_provenance,
    parse_chunk_rows,
    parse_document_rows,
    parse_external_stub_rows,
    parse_provision_rows,
)
from .traversal import GraphTraversal, TraversalMode, TraversalResult


@dataclass(frozen=True)
class ParsedGraphSources:
    """Typed v2 graph source records ready for building or overlay joins."""

    documents: tuple[DocumentNode, ...]
    external_stubs: tuple[ExternalStubNode, ...]
    provisions: tuple[ProvisionNode, ...]
    chunks: tuple[ChunkNode, ...]
    edges: tuple[GraphEdge, ...]
    text_provenance: dict[str, TextProvenanceRecord]


class KnowledgeGraphFacade:
    """Public orchestration surface for the v2 knowledge graph module.

    The facade coordinates the existing graph services but keeps the
    responsibilities separated: loading, parsing, graph building, traversal,
    overlay joins, and graph-guided context construction.
    """

    def __init__(
        self,
        paths: GraphLoaderPaths | None = None,
        loader: GraphLoader | None = None,
        builder: GraphBuilder | None = None,
        overlay_joiner: OverlayJoiner | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.paths = paths or GraphLoaderPaths()
        self.loader = loader or GraphLoader(self.paths)
        self.builder = builder or GraphBuilder()
        self.overlay_joiner = overlay_joiner or OverlayJoiner()
        self.context_builder = context_builder or ContextBuilder()

    def load_sources(self) -> GraphSourceBundle:
        """Load the five graph source streams allowed by the loader contract."""

        return self.loader.load_all()

    def parse_sources(self) -> ParsedGraphSources:
        """Load and parse the v2 graph source files into typed records."""

        sources = self.load_sources()
        document_rows = tuple(sources.documents)
        text_provenance = index_text_provenance(document_rows)
        documents = tuple(parse_document_rows(document_rows, text_provenance))
        external_stubs = tuple(parse_external_stub_rows(sources.external_stubs))
        provisions = tuple(parse_provision_rows(sources.provisions))
        chunks = tuple(parse_chunk_rows(sources.chunks))
        edges = tuple(parse_edge_rows(sources.edges))
        return ParsedGraphSources(
            documents=documents,
            external_stubs=external_stubs,
            provisions=provisions,
            chunks=chunks,
            edges=edges,
            text_provenance=text_provenance,
        )

    def build_graph(self) -> GraphBuildResult:
        """Parse the v2 source files and build an in-memory knowledge graph."""

        parsed = self.parse_sources()
        return self.builder.build(
            documents=parsed.documents,
            external_stubs=parsed.external_stubs,
            provisions=parsed.provisions,
            chunks=parsed.chunks,
            edges=parsed.edges,
        )

    def build_traversal(self, graph: KnowledgeGraph) -> GraphTraversal:
        """Create a traversal service for an already built knowledge graph."""

        return GraphTraversal(graph)

    def traverse(self, graph: KnowledgeGraph, start_id: str, mode: TraversalMode, max_depth: int = 3) -> TraversalResult:
        """Traverse a built graph using one of the supported traversal modes."""

        return self.build_traversal(graph).traverse(start_id, mode, max_depth=max_depth)

    def build_overlay_bundle(
        self,
        *,
        documents: Iterable[DocumentNode],
        validity_events: Iterable[ValidityEvent],
        authority_entries: Iterable[AuthorityIndexEntry],
        as_of_date: str | None = None,
    ) -> OverlayBundle:
        """Join validity and authority overlays onto documents without mutation."""

        return self.overlay_joiner.build_bundle(
            documents=documents,
            validity_events=validity_events,
            authority_entries=authority_entries,
            as_of_date=as_of_date,
        )

    def build_validity_overlay(
        self,
        documents: Iterable[DocumentNode],
        validity_events: Iterable[ValidityEvent],
        as_of_date: str | None = None,
    ) -> dict[str, DocumentOverlay]:
        """Join only validity overlay data onto documents."""

        return self.overlay_joiner.join_validity_overlay(documents, validity_events, as_of_date=as_of_date)

    def build_authority_overlay(
        self,
        documents: Iterable[DocumentNode],
        authority_entries: Iterable[AuthorityIndexEntry],
    ) -> dict[str, DocumentOverlay]:
        """Join only authority overlay data onto documents."""

        return self.overlay_joiner.join_authority_overlay(documents, authority_entries)

    def build_graph_guided_filter(
        self,
        *,
        graph: KnowledgeGraph,
        traversal: TraversalResult,
        overlays: dict[str, DocumentOverlay],
        filter_profile: FilterProfile = "current_law",
        constraints: QueryConstraints | None = None,
    ) -> GraphGuidedFilter:
        """Construct the graph-guided `id_str` filter for retrieval."""

        return self.context_builder.build_graph_guided_filter(
            graph=graph,
            traversal=traversal,
            overlays=overlays,
            filter_profile=filter_profile,
            constraints=constraints,
        )

    def build_evidence_context(
        self,
        *,
        graph: KnowledgeGraph,
        traversal: TraversalResult,
        overlays: dict[str, DocumentOverlay],
        filter_profile: FilterProfile = "current_law",
        constraints: QueryConstraints | None = None,
    ) -> EvidenceContext:
        """Construct the full evidence bundle used by retrieval and answering."""

        return self.context_builder.build_evidence_context(
            graph=graph,
            traversal=traversal,
            overlays=overlays,
            filter_profile=filter_profile,
            constraints=constraints,
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
        """Return the candidate document IDs suitable for citation display."""

        return self.context_builder.build_citation_context(
            graph=graph,
            traversal=traversal,
            overlays=overlays,
            filter_profile=filter_profile,
            constraints=constraints,
        )

    def build_empty_filter_response(self, filter_profile: FilterProfile, reason: str) -> GraphGuidedFilter:
        """Return an explicit empty graph-guided filter response."""

        return self.context_builder.build_empty_response(filter_profile=filter_profile, reason=reason)
