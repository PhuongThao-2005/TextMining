from __future__ import annotations

from dataclasses import dataclass

from .builder import KnowledgeGraph
from .expansion_schema import ExpansionResult, ExpansionStep


@dataclass(frozen=True)
class _ProvisionWindow:
    """Internal ordered chunk window anchored to one provision."""

    provision_id: str
    document_id: str
    chunk_ids: tuple[str, ...]


class GraphExpansion:
    """Expand seed chunk IDs into ordered local context.

    The expansion algorithm is deliberately local and adjacency-driven. It uses
    the graph's precomputed provision/chunk adjacency and ordered chunk lists,
    so it remains efficient on large corpora and does not scan the dataset.
    """

    def __init__(self, graph: KnowledgeGraph) -> None:
        self.graph = graph
        self._ordered_chunks_cache: dict[str, tuple[str, ...]] = {}

    def expand(
        self,
        seed_chunk_ids: list[str] | tuple[str, ...],
        max_hop: int | None = None,
        max_context: int | None = None,
    ) -> ExpansionResult:
        """Expand seed chunks into a bounded, reading-order-preserving context.

        Parameters
        ----------
        seed_chunk_ids:
            One or more seed chunk IDs to expand.
        max_hop:
            Optional structural hop budget. Hop 1 covers the seed chunk's own
            provision; hop 2 adds the next provision; subsequent hops continue
            along `PROVISION_NEXT`.
        max_context:
            Optional cap on the total number of ordered context chunks returned.
        """

        max_hop = 1 if max_hop is None else max(1, int(max_hop))
        seeds = tuple(dict.fromkeys(str(chunk_id) for chunk_id in seed_chunk_ids if str(chunk_id)))
        if not seeds:
            return ExpansionResult(
                seed_chunk_ids=(),
                max_hop=max_hop,
                max_context=max_context,
                expanded_node_ids=(),
                traversed_edges=(),
                ordered_context_chunks=(),
                warnings=("No seed chunk IDs were supplied.",),
            )

        expanded_node_ids: list[str] = []
        traversed_edges: list[ExpansionStep] = []
        ordered_context_chunks: list[str] = []
        warnings: list[str] = []

        for seed_id in seeds:
            chunk = self.graph.chunks.get(seed_id)
            if chunk is None:
                warnings.append(f"Missing seed chunk: {seed_id}")
                continue

            provision_id = chunk.parent_unit_id
            if not provision_id:
                warnings.append(f"Seed chunk has no parent provision: {seed_id}")
                expanded_node_ids.append(seed_id)
                ordered_context_chunks.append(seed_id)
                continue

            document_id = self.graph.provisions.get(provision_id).id_str if self.graph.provisions.get(provision_id) else ""
            if not document_id:
                warnings.append(f"Missing parent provision for seed chunk: {seed_id}")
                expanded_node_ids.append(seed_id)
                ordered_context_chunks.append(seed_id)
                continue

            current_window = self._build_current_window(provision_id, document_id, seed_id, max_context)
            provision_chain = self._build_provision_chain(provision_id, max_hop=max_hop)

            expanded_node_ids.append(document_id)
            expanded_node_ids.append(provision_id)
            expanded_node_ids.extend(current_window.chunk_ids)

            traversed_edges.append(
                ExpansionStep(
                    src_id=document_id,
                    dst_id=provision_id,
                    rel_type="DOCUMENT_HAS_PROVISION",
                    provenance={"id_str": document_id, "unit_id": provision_id},
                )
            )
            traversed_edges.extend(self._chunk_window_steps(provision_id, current_window.chunk_ids))

            ordered_context_chunks.extend(current_window.chunk_ids)

            previous_provision_id = provision_id
            for next_window in provision_chain[1:]:
                expanded_node_ids.append(next_window.provision_id)
                expanded_node_ids.extend(next_window.chunk_ids)
                traversed_edges.append(
                    ExpansionStep(
                        src_id=previous_provision_id,
                        dst_id=next_window.provision_id,
                        rel_type="PROVISION_NEXT",
                        provenance={"from": previous_provision_id, "to": next_window.provision_id},
                    )
                )
                traversed_edges.extend(self._chunk_window_steps(next_window.provision_id, next_window.chunk_ids))
                ordered_context_chunks.extend(next_window.chunk_ids)
                previous_provision_id = next_window.provision_id

        expanded_node_ids = self._dedupe_preserve_order(expanded_node_ids)
        ordered_context_chunks = self._dedupe_preserve_order(ordered_context_chunks)
        if max_context is not None and max_context >= 0:
            ordered_context_chunks = ordered_context_chunks[:max_context]
        traversed_edges = self._dedupe_steps(traversed_edges)

        return ExpansionResult(
            seed_chunk_ids=seeds,
            max_hop=max_hop,
            max_context=max_context,
            expanded_node_ids=tuple(expanded_node_ids),
            traversed_edges=tuple(traversed_edges),
            ordered_context_chunks=tuple(ordered_context_chunks),
            warnings=tuple(warnings),
        )

    def _build_current_window(
        self,
        provision_id: str,
        document_id: str,
        seed_chunk_id: str,
        max_context: int | None,
    ) -> _ProvisionWindow:
        """Build the reading-order chunk window for the seed's own provision."""

        ordered_chunks = self._ordered_chunks_for_provision(provision_id)
        if not ordered_chunks:
            return _ProvisionWindow(provision_id=provision_id, document_id=document_id, chunk_ids=(seed_chunk_id,))

        seed_index = self._chunk_index(ordered_chunks, seed_chunk_id)
        if seed_index is None:
            seed_index = 0

        if max_context is None or max_context <= 0 or max_context >= len(ordered_chunks):
            chunk_ids = ordered_chunks
        else:
            left = max_context // 2
            right = max_context - left - 1
            start = max(0, seed_index - left)
            end = min(len(ordered_chunks), seed_index + right + 1)
            if end - start < max_context:
                deficit = max_context - (end - start)
                start = max(0, start - deficit)
                end = min(len(ordered_chunks), end + (max_context - (end - start)))
            chunk_ids = ordered_chunks[start:end]

        return _ProvisionWindow(provision_id=provision_id, document_id=document_id, chunk_ids=chunk_ids)

    def _build_provision_chain(self, start_provision_id: str, max_hop: int) -> tuple[_ProvisionWindow, ...]:
        """Build a forward-only provision chain using `PROVISION_NEXT`.

        Hop 1 is the seed provision. Additional hops follow the forward reading
        order only, which keeps the walk bounded and avoids corpus-wide scans.
        """

        windows: list[_ProvisionWindow] = []
        current_provision_id = start_provision_id
        current_document_id = self.graph.provisions.get(start_provision_id).id_str if self.graph.provisions.get(start_provision_id) else ""
        for hop in range(max_hop):
            ordered_chunks = self._ordered_chunks_for_provision(current_provision_id)
            windows.append(
                _ProvisionWindow(
                    provision_id=current_provision_id,
                    document_id=current_document_id,
                    chunk_ids=ordered_chunks,
                )
            )
            next_provision_id = self.graph.provision_next.get(current_provision_id)
            if not next_provision_id:
                break
            current_provision_id = next_provision_id
        return tuple(windows)

    def _ordered_chunks_for_provision(self, provision_id: str) -> tuple[str, ...]:
        """Return chunk IDs for a provision in reading order.

        The order is derived from the chunk metadata already loaded into the
        graph and cached per provision for repeated expansion calls.
        """

        cached = self._ordered_chunks_cache.get(provision_id)
        if cached is not None:
            return cached

        chunk_ids = tuple(self.graph.provision_to_chunks.get(provision_id, ()))
        if not chunk_ids:
            self._ordered_chunks_cache[provision_id] = ()
            return ()

        ordered = tuple(
            sorted(
                chunk_ids,
                key=lambda chunk_id: (
                    self.graph.chunks.get(chunk_id).chunk_index_in_unit if self.graph.chunks.get(chunk_id) else 0,
                    chunk_id,
                ),
            )
        )
        self._ordered_chunks_cache[provision_id] = ordered
        return ordered

    @staticmethod
    def _chunk_index(chunk_ids: tuple[str, ...], chunk_id: str) -> int | None:
        """Return the zero-based reading-order index of a chunk within its provision."""

        try:
            return chunk_ids.index(chunk_id)
        except ValueError:
            return None

    @staticmethod
    def _chunk_window_steps(provision_id: str, chunk_ids: tuple[str, ...]) -> list[ExpansionStep]:
        """Build the `PROVISION_HAS_CHUNK` and `CHUNK_NEXT` edges for an ordered chunk window."""

        steps: list[ExpansionStep] = []
        for chunk_id in chunk_ids:
            steps.append(
                ExpansionStep(
                    src_id=provision_id,
                    dst_id=chunk_id,
                    rel_type="PROVISION_HAS_CHUNK",
                    provenance={"parent_unit_id": provision_id, "chunk_id": chunk_id},
                )
            )
        for left, right in zip(chunk_ids, chunk_ids[1:]):
            steps.append(
                ExpansionStep(
                    src_id=left,
                    dst_id=right,
                    rel_type="CHUNK_NEXT",
                    provenance={"parent_unit_id": provision_id, "from": left, "to": right},
                )
            )
        return steps

    @staticmethod
    def _dedupe_preserve_order(items: list[str]) -> list[str]:
        """Remove duplicates while preserving first-seen order."""

        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    @staticmethod
    def _dedupe_steps(steps: list[ExpansionStep]) -> list[ExpansionStep]:
        """Deduplicate traversal steps while preserving first-seen order."""

        seen: set[tuple[str, str, str]] = set()
        ordered: list[ExpansionStep] = []
        for step in steps:
            key = (step.src_id, step.dst_id, step.rel_type)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(step)
        return ordered
