from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .edge_schema import GraphEdge
from .parser import ChunkNode, DocumentNode, ExternalStubNode, ProvisionNode
@dataclass(frozen=True)
class StructuralEdge:
    """Materialized structural relationship edge inside the graph."""

    edge_id: str
    src_id: str
    dst_id: str
    rel_type: str
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeGraph:
    """In-memory v2 knowledge graph assembled from typed source records."""

    documents: dict[str, DocumentNode]
    external_stubs: dict[str, ExternalStubNode]
    provisions: dict[str, ProvisionNode]
    chunks: dict[str, ChunkNode]
    document_edges: tuple[GraphEdge, ...]
    verified_document_edges: tuple[GraphEdge, ...]
    structural_edges: tuple[StructuralEdge, ...]
    document_to_provisions: dict[str, tuple[str, ...]]
    provision_to_chunks: dict[str, tuple[str, ...]]
    provision_next: dict[str, str]
    chunk_next: dict[str, str]


@dataclass(frozen=True)
class GraphBuildStats:
    """Summary counts produced while assembling the graph."""

    document_count: int
    external_stub_count: int
    provision_count: int
    chunk_count: int
    document_edge_count: int
    verified_document_edge_count: int
    unverified_document_edge_count: int
    structural_edge_count: int
    orphan_provision_count: int
    orphan_chunk_count: int
    missing_external_stub_count: int
    structural_edge_counts: dict[str, int]
    edge_group_counts: dict[str, int]


@dataclass(frozen=True)
class GraphBuildResult:
    """Combined graph and summary information returned by the builder."""

    graph: KnowledgeGraph
    stats: GraphBuildStats
    warnings: tuple[str, ...]


class GraphBuilder:
    """Assemble typed v2 records into an in-memory graph representation.

    The builder materializes the four structural edge types from the spec and
    preserves document edges in both raw and verified views. It does not join
    overlay files and it does not perform traversal.
    """

    def build(
        self,
        *,
        documents: Iterable[DocumentNode],
        external_stubs: Iterable[ExternalStubNode],
        provisions: Iterable[ProvisionNode],
        chunks: Iterable[ChunkNode],
        edges: Iterable[GraphEdge],
    ) -> GraphBuildResult:
        """Build an in-memory knowledge graph from parsed source records."""

        document_map = self._index_unique(documents, "id_str")
        external_stub_map = self._index_unique(external_stubs, "id_str")
        provision_map = self._index_unique(provisions, "unit_id")
        chunk_map = self._index_unique(chunks, "chunk_id")
        edge_list = tuple(edges)

        warnings: list[str] = []
        structural_edges: list[StructuralEdge] = []

        document_to_provisions, provision_orphans, provision_structure_edges = self._build_document_provision_links(
            document_map, provision_map
        )
        provision_to_chunks, chunk_orphans, chunk_structure_edges = self._build_provision_chunk_links(
            provision_map, chunk_map
        )
        provision_next, chunk_next, ordering_warnings, order_structure_edges = self._build_reading_order_links(
            provision_map, chunk_map
        )

        warnings.extend(provision_orphans)
        warnings.extend(chunk_orphans)
        warnings.extend(ordering_warnings)
        structural_edges.extend(provision_structure_edges)
        structural_edges.extend(chunk_structure_edges)
        structural_edges.extend(order_structure_edges)

        verified_edges = tuple(edge for edge in edge_list if edge.direction_verified)
        unverified_edges = tuple(edge for edge in edge_list if not edge.direction_verified)
        edge_group_counts = self._count_edge_groups(edge_list)
        structural_edge_counts = Counter(edge.rel_type for edge in structural_edges)

        missing_external_stub_count = self._count_missing_external_targets(edge_list, document_map, external_stub_map)

        graph = KnowledgeGraph(
            documents=document_map,
            external_stubs=external_stub_map,
            provisions=provision_map,
            chunks=chunk_map,
            document_edges=edge_list,
            verified_document_edges=verified_edges,
            structural_edges=tuple(structural_edges),
            document_to_provisions=document_to_provisions,
            provision_to_chunks=provision_to_chunks,
            provision_next=provision_next,
            chunk_next=chunk_next,
        )
        stats = GraphBuildStats(
            document_count=len(document_map),
            external_stub_count=len(external_stub_map),
            provision_count=len(provision_map),
            chunk_count=len(chunk_map),
            document_edge_count=len(edge_list),
            verified_document_edge_count=len(verified_edges),
            unverified_document_edge_count=len(unverified_edges),
            structural_edge_count=len(structural_edges),
            orphan_provision_count=len(provision_orphans),
            orphan_chunk_count=len(chunk_orphans),
            missing_external_stub_count=missing_external_stub_count,
            structural_edge_counts=dict(structural_edge_counts),
            edge_group_counts=dict(edge_group_counts),
        )
        return GraphBuildResult(graph=graph, stats=stats, warnings=tuple(warnings))

    @staticmethod
    def _index_unique(items: Iterable[Any], key_name: str) -> dict[str, Any]:
        """Index items by a named attribute and reject duplicate identifiers."""

        out: dict[str, Any] = {}
        duplicates: list[str] = []
        for item in items:
            key = str(getattr(item, key_name) or "")
            if not key:
                continue
            if key in out:
                duplicates.append(key)
                continue
            out[key] = item
        if duplicates:
            joined = ", ".join(sorted(set(duplicates)))
            raise ValueError(f"Duplicate graph identifiers for {key_name}: {joined}")
        return out

    @staticmethod
    def _build_document_provision_links(
        documents: dict[str, DocumentNode],
        provisions: dict[str, ProvisionNode],
    ) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...], tuple[StructuralEdge, ...]]:
        """Build DOCUMENT_HAS_PROVISION edges and adjacency."""

        adjacency: dict[str, list[str]] = defaultdict(list)
        structural_edges: list[StructuralEdge] = []
        orphans: list[str] = []
        for provision in provisions.values():
            if provision.id_str not in documents:
                orphans.append(provision.unit_id)
                continue
            adjacency[provision.id_str].append(provision.unit_id)
            structural_edges.append(
                StructuralEdge(
                    edge_id=f"{provision.id_str}->{provision.unit_id}::DOCUMENT_HAS_PROVISION",
                    src_id=provision.id_str,
                    dst_id=provision.unit_id,
                    rel_type="DOCUMENT_HAS_PROVISION",
                    provenance={"id_str": provision.id_str, "unit_id": provision.unit_id},
                )
            )
        return (
            {key: tuple(values) for key, values in adjacency.items()},
            tuple(orphans),
            tuple(structural_edges),
        )

    @staticmethod
    def _build_provision_chunk_links(
        provisions: dict[str, ProvisionNode],
        chunks: dict[str, ChunkNode],
    ) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...], tuple[StructuralEdge, ...]]:
        """Build PROVISION_HAS_CHUNK edges and adjacency."""

        adjacency: dict[str, list[str]] = defaultdict(list)
        structural_edges: list[StructuralEdge] = []
        orphans: list[str] = []
        for chunk in chunks.values():
            if chunk.parent_unit_id not in provisions:
                orphans.append(chunk.chunk_id)
                continue
            adjacency[chunk.parent_unit_id].append(chunk.chunk_id)
            structural_edges.append(
                StructuralEdge(
                    edge_id=f"{chunk.parent_unit_id}->{chunk.chunk_id}::PROVISION_HAS_CHUNK",
                    src_id=chunk.parent_unit_id,
                    dst_id=chunk.chunk_id,
                    rel_type="PROVISION_HAS_CHUNK",
                    provenance={"parent_unit_id": chunk.parent_unit_id, "chunk_id": chunk.chunk_id},
                )
            )
        return (
            {key: tuple(values) for key, values in adjacency.items()},
            tuple(orphans),
            tuple(structural_edges),
        )

    @staticmethod
    def _build_reading_order_links(
        provisions: dict[str, ProvisionNode],
        chunks: dict[str, ChunkNode],
    ) -> tuple[dict[str, str], dict[str, str], tuple[str, ...], tuple[StructuralEdge, ...]]:
        """Build the materialized PROVISION_NEXT and CHUNK_NEXT edges."""

        provision_next: dict[str, str] = {}
        chunk_next: dict[str, str] = {}
        structural_edges: list[StructuralEdge] = []
        warnings: list[str] = []

        provisions_by_doc: dict[str, list[ProvisionNode]] = defaultdict(list)
        for provision in provisions.values():
            if provision.id_str:
                provisions_by_doc[provision.id_str].append(provision)
        for id_str, ordered in provisions_by_doc.items():
            ordered.sort(key=lambda item: (item.char_start, item.unit_id))
            for index, current in enumerate(ordered[:-1]):
                nxt = ordered[index + 1]
                provision_next[current.unit_id] = nxt.unit_id
                structural_edges.append(
                    StructuralEdge(
                        edge_id=f"{current.unit_id}->{nxt.unit_id}::PROVISION_NEXT",
                        src_id=current.unit_id,
                        dst_id=nxt.unit_id,
                        rel_type="PROVISION_NEXT",
                        provenance={"id_str": id_str, "from": current.unit_id, "to": nxt.unit_id},
                    )
                )

        chunks_by_provision: dict[str, list[ChunkNode]] = defaultdict(list)
        for chunk in chunks.values():
            if chunk.parent_unit_id:
                chunks_by_provision[chunk.parent_unit_id].append(chunk)
        for parent_unit_id, ordered in chunks_by_provision.items():
            ordered.sort(key=lambda item: (item.chunk_index_in_unit, item.chunk_id))
            for index, current in enumerate(ordered[:-1]):
                nxt = ordered[index + 1]
                chunk_next[current.chunk_id] = nxt.chunk_id
                structural_edges.append(
                    StructuralEdge(
                        edge_id=f"{current.chunk_id}->{nxt.chunk_id}::CHUNK_NEXT",
                        src_id=current.chunk_id,
                        dst_id=nxt.chunk_id,
                        rel_type="CHUNK_NEXT",
                        provenance={"parent_unit_id": parent_unit_id, "from": current.chunk_id, "to": nxt.chunk_id},
                    )
                )

        if not provisions_by_doc:
            warnings.append("No provisions were available to derive PROVISION_NEXT edges.")
        if not chunks_by_provision:
            warnings.append("No chunks were available to derive CHUNK_NEXT edges.")

        return provision_next, chunk_next, tuple(warnings), tuple(structural_edges)

    @staticmethod
    def _count_edge_groups(edges: Iterable[GraphEdge]) -> Counter[str]:
        """Count edges by relationship group."""

        counter: Counter[str] = Counter()
        for edge in edges:
            counter[edge.rel_group or "unknown"] += 1
        return counter

    @staticmethod
    def _count_missing_external_targets(
        edges: Iterable[GraphEdge],
        documents: dict[str, DocumentNode],
        external_stubs: dict[str, ExternalStubNode],
    ) -> int:
        """Count external-target edges whose destination is not a known stub or document."""

        missing = 0
        for edge in edges:
            if edge.external_target and edge.dst_id not in documents and edge.dst_id not in external_stubs:
                missing += 1
        return missing