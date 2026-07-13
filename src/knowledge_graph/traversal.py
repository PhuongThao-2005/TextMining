from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Literal

from .builder import KnowledgeGraph
from .edge_schema import GraphEdge


TraversalMode = Literal["basis", "guidance", "validity", "structure", "neighbors"]


@dataclass(frozen=True)
class TraversalStep:
    """One hop in a traversal path."""

    src_id: str
    dst_id: str
    rel_type: str
    provenance: dict[str, Any]


@dataclass(frozen=True)
class TraversalPath:
    """Ordered traversal path returned by the traversal engine."""

    start_id: str
    end_id: str
    steps: tuple[TraversalStep, ...]


@dataclass(frozen=True)
class TraversalResult:
    """Traversal output containing visited IDs, edges, and paths."""

    start_id: str
    mode: str
    max_depth: int
    visited_ids: tuple[str, ...]
    visited_edges: tuple[TraversalStep, ...]
    paths: tuple[TraversalPath, ...]


class GraphTraversal:
    """Traverse the v2 knowledge graph using only verified relationships.

    This service is intentionally read-only. It does not perform overlay joins,
    currency evaluation, or graph mutation.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self._document_adjacency = self._build_document_adjacency(graph.verified_document_edges)

    def traverse_basis(self, start_id: str, max_depth: int = 3) -> TraversalResult:
        """Traverse verified `BASED_ON` edges from a starting document."""

        return self._traverse_cross_document(start_id, "basis", {"basis"}, max_depth)

    def traverse_guidance(self, start_id: str, max_depth: int = 3) -> TraversalResult:
        """Traverse verified guidance edges from a starting document."""

        return self._traverse_cross_document(start_id, "guidance", {"guidance"}, max_depth)

    def traverse_validity(self, start_id: str, max_depth: int = 3) -> TraversalResult:
        """Traverse verified validity edges from a starting document.

        Currency reasoning is intentionally out of scope here; this method only
        returns the verified validity lineage present in the graph edges.
        """

        return self._traverse_cross_document(start_id, "validity", {"validity"}, max_depth)

    def traverse_structure(self, start_id: str, max_depth: int = 3) -> TraversalResult:
        """Traverse the structural Document -> Provision -> Chunk hierarchy."""

        if start_id in self.graph.documents:
            return self._traverse_structure_from_document(start_id, max_depth)
        if start_id in self.graph.provisions:
            return self._traverse_structure_from_provision(start_id, max_depth)
        if start_id in self.graph.chunks:
            return self._traverse_structure_from_chunk(start_id, max_depth)
        return TraversalResult(start_id=start_id, mode="structure", max_depth=max_depth, visited_ids=(), visited_edges=(), paths=())

    def traverse_neighbors(self, start_id: str, max_depth: int = 1) -> TraversalResult:
        """Traverse all verified outgoing cross-document edges within a depth cap."""

        return self._traverse_cross_document(start_id, "neighbors", None, max_depth)

    def traverse(
        self,
        start_id: str,
        mode: TraversalMode,
        max_depth: int = 3,
    ) -> TraversalResult:
        """Dispatch to a traversal mode-specific method."""

        if mode == "basis":
            return self.traverse_basis(start_id, max_depth=max_depth)
        if mode == "guidance":
            return self.traverse_guidance(start_id, max_depth=max_depth)
        if mode == "validity":
            return self.traverse_validity(start_id, max_depth=max_depth)
        if mode == "structure":
            return self.traverse_structure(start_id, max_depth=max_depth)
        return self.traverse_neighbors(start_id, max_depth=max_depth)

    def _traverse_cross_document(
        self,
        start_id: str,
        mode: str,
        rel_groups: set[str] | None,
        max_depth: int,
    ) -> TraversalResult:
        """Traverse verified cross-document edges by relationship group."""

        if max_depth < 1:
            return TraversalResult(start_id=start_id, mode=mode, max_depth=max_depth, visited_ids=(start_id,), visited_edges=(), paths=())

        visited_ids = {start_id}
        visited_edges: list[TraversalStep] = []
        paths: list[TraversalPath] = []
        queue = deque([(start_id, tuple())])

        while queue:
            current_id, current_steps = queue.popleft()
            depth = len(current_steps)
            if depth >= max_depth:
                continue
            for edge in self._document_adjacency.get(current_id, ()):
                if rel_groups is not None and edge.rel_group not in rel_groups:
                    continue
                step = TraversalStep(
                    src_id=edge.src_id,
                    dst_id=edge.dst_id,
                    rel_type=edge.rel_canonical,
                    provenance=dict(edge.provenance),
                )
                next_steps = current_steps + (step,)
                visited_edges.append(step)
                visited_ids.add(edge.dst_id)
                paths.append(TraversalPath(start_id=start_id, end_id=edge.dst_id, steps=next_steps))
                if len(next_steps) < max_depth:
                    queue.append((edge.dst_id, next_steps))

        return TraversalResult(
            start_id=start_id,
            mode=mode,
            max_depth=max_depth,
            visited_ids=tuple(visited_ids),
            visited_edges=tuple(self._dedupe_steps(visited_edges)),
            paths=tuple(paths),
        )

    def _traverse_structure_from_document(self, document_id: str, max_depth: int) -> TraversalResult:
        """Traverse from a document into its provisions and chunks."""

        if max_depth < 1:
            return TraversalResult(start_id=document_id, mode="structure", max_depth=max_depth, visited_ids=(document_id,), visited_edges=(), paths=())

        visited_ids = {document_id}
        visited_edges: list[TraversalStep] = []
        paths: list[TraversalPath] = []

        for provision_id in self.graph.document_to_provisions.get(document_id, ()):
            provision_step = TraversalStep(
                src_id=document_id,
                dst_id=provision_id,
                rel_type="DOCUMENT_HAS_PROVISION",
                provenance={"id_str": document_id, "unit_id": provision_id},
            )
            visited_edges.append(provision_step)
            visited_ids.add(provision_id)
            paths.append(TraversalPath(start_id=document_id, end_id=provision_id, steps=(provision_step,)))
            if max_depth > 1:
                for chunk_id in self.graph.provision_to_chunks.get(provision_id, ()):
                    chunk_step = TraversalStep(
                        src_id=provision_id,
                        dst_id=chunk_id,
                        rel_type="PROVISION_HAS_CHUNK",
                        provenance={"parent_unit_id": provision_id, "chunk_id": chunk_id},
                    )
                    visited_edges.append(chunk_step)
                    visited_ids.add(chunk_id)
                    paths.append(TraversalPath(start_id=document_id, end_id=chunk_id, steps=(provision_step, chunk_step)))

        return TraversalResult(
            start_id=document_id,
            mode="structure",
            max_depth=max_depth,
            visited_ids=tuple(visited_ids),
            visited_edges=tuple(self._dedupe_steps(visited_edges)),
            paths=tuple(paths),
        )

    def _traverse_structure_from_provision(self, provision_id: str, max_depth: int) -> TraversalResult:
        """Traverse from a provision to its chunks and neighboring provisions."""

        if max_depth < 1:
            return TraversalResult(start_id=provision_id, mode="structure", max_depth=max_depth, visited_ids=(provision_id,), visited_edges=(), paths=())

        visited_ids = {provision_id}
        visited_edges: list[TraversalStep] = []
        paths: list[TraversalPath] = []

        for chunk_id in self.graph.provision_to_chunks.get(provision_id, ()):
            chunk_step = TraversalStep(
                src_id=provision_id,
                dst_id=chunk_id,
                rel_type="PROVISION_HAS_CHUNK",
                provenance={"parent_unit_id": provision_id, "chunk_id": chunk_id},
            )
            visited_edges.append(chunk_step)
            visited_ids.add(chunk_id)
            paths.append(TraversalPath(start_id=provision_id, end_id=chunk_id, steps=(chunk_step,)))

        next_provision_id = self.graph.provision_next.get(provision_id)
        if max_depth > 1 and next_provision_id:
            next_step = TraversalStep(
                src_id=provision_id,
                dst_id=next_provision_id,
                rel_type="PROVISION_NEXT",
                provenance={"from": provision_id, "to": next_provision_id},
            )
            visited_edges.append(next_step)
            visited_ids.add(next_provision_id)
            paths.append(TraversalPath(start_id=provision_id, end_id=next_provision_id, steps=(next_step,)))

        return TraversalResult(
            start_id=provision_id,
            mode="structure",
            max_depth=max_depth,
            visited_ids=tuple(visited_ids),
            visited_edges=tuple(self._dedupe_steps(visited_edges)),
            paths=tuple(paths),
        )

    def _traverse_structure_from_chunk(self, chunk_id: str, max_depth: int) -> TraversalResult:
        """Traverse from a chunk to its siblings and parent provision."""

        if max_depth < 1:
            return TraversalResult(start_id=chunk_id, mode="structure", max_depth=max_depth, visited_ids=(chunk_id,), visited_edges=(), paths=())

        chunk = self.graph.chunks.get(chunk_id)
        if chunk is None:
            return TraversalResult(start_id=chunk_id, mode="structure", max_depth=max_depth, visited_ids=(), visited_edges=(), paths=())

        visited_ids = {chunk_id}
        visited_edges: list[TraversalStep] = []
        paths: list[TraversalPath] = []

        parent_unit_id = chunk.parent_unit_id
        if parent_unit_id:
            parent_step = TraversalStep(
                src_id=chunk_id,
                dst_id=parent_unit_id,
                rel_type="PROVISION_HAS_CHUNK",
                provenance={"parent_unit_id": parent_unit_id, "chunk_id": chunk_id},
            )
            visited_edges.append(parent_step)
            visited_ids.add(parent_unit_id)
            paths.append(TraversalPath(start_id=chunk_id, end_id=parent_unit_id, steps=(parent_step,)))

            for sibling_chunk_id in self.graph.provision_to_chunks.get(parent_unit_id, ()):
                if sibling_chunk_id == chunk_id:
                    continue
                sibling_step = TraversalStep(
                    src_id=parent_unit_id,
                    dst_id=sibling_chunk_id,
                    rel_type="PROVISION_HAS_CHUNK",
                    provenance={"parent_unit_id": parent_unit_id, "chunk_id": sibling_chunk_id},
                )
                visited_edges.append(sibling_step)
                visited_ids.add(sibling_chunk_id)
                paths.append(TraversalPath(start_id=chunk_id, end_id=sibling_chunk_id, steps=(parent_step, sibling_step)))

        return TraversalResult(
            start_id=chunk_id,
            mode="structure",
            max_depth=max_depth,
            visited_ids=tuple(visited_ids),
            visited_edges=tuple(self._dedupe_steps(visited_edges)),
            paths=tuple(paths),
        )

    @staticmethod
    def _build_document_adjacency(edges: tuple[GraphEdge, ...]) -> dict[str, tuple[GraphEdge, ...]]:
        """Build a source-ID adjacency map over verified document edges."""

        adjacency: dict[str, list[GraphEdge]] = {}
        for edge in edges:
            adjacency.setdefault(edge.src_id, []).append(edge)
        return {key: tuple(value) for key, value in adjacency.items()}

    @staticmethod
    def _dedupe_steps(steps: list[TraversalStep]) -> list[TraversalStep]:
        """Deduplicate traversal steps while preserving first-seen order."""

        seen: set[tuple[str, str, str]] = set()
        deduped: list[TraversalStep] = []
        for step in steps:
            key = (step.src_id, step.dst_id, step.rel_type)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(step)
        return deduped
