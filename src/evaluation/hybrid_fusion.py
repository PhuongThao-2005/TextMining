"""Pure helpers for mapping a vector pre-pass to graph traversal starts and
fusing hybrid retrieval candidates.

Per data-model.md §2.5/§2.7. These functions never read `ground_truth.*`
fields (FR-003g) and never re-rank fused output (FR-003d).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from retrieval.schema import RetrievedChunk

CROSS_DOCUMENT_MODES = {"basis", "guidance", "validity"}


@dataclass(frozen=True)
class TraversalStartSet:
    """Result of mapping an unfiltered vector pre-pass to graph traversal starts."""

    prepass_chunk_ids: tuple[str, ...]
    start_ids: tuple[str, ...]
    mode: str
    capped: bool
    empty: bool


@dataclass(frozen=True)
class HybridFusionResult:
    """Output of the pure fusion helper (research R6)."""

    retrieved_chunk_ids: tuple[str, ...]
    seed_count: int
    expansion_added: tuple[str, ...]
    traversal_added: tuple[str, ...]


def _dedupe_preserve_order(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _start_id_for(hit: RetrievedChunk, mode: str) -> str | None:
    if mode in CROSS_DOCUMENT_MODES:
        return hit.id_str or None
    if mode == "structure":
        return hit.parent_unit_id or hit.id_str or None
    # "neighbors" and any other mode default to chunk-level starts.
    return hit.chunk_id or None


def build_traversal_starts(
    prepass_hits: Sequence[RetrievedChunk],
    mode: str,
    max_starts: int,
) -> TraversalStartSet:
    """Deterministically map unfiltered vector pre-pass hits to graph start IDs.

    Uses document `id_str` for cross-document modes (`basis`/`guidance`/
    `validity`), provision/document `parent_unit_id` for `structure`, and
    chunk id otherwise. Dedupe keep-first, cap at `max_starts`. Never reads
    or accepts any `ground_truth.*` field (FR-003g).
    """

    prepass_chunk_ids = tuple(hit.chunk_id for hit in prepass_hits if hit.chunk_id)

    candidate_ids = [_start_id_for(hit, mode) for hit in prepass_hits]
    deduped = _dedupe_preserve_order([cid for cid in candidate_ids if cid])
    capped = len(deduped) > max_starts
    start_ids = tuple(deduped[:max_starts])

    return TraversalStartSet(
        prepass_chunk_ids=prepass_chunk_ids,
        start_ids=start_ids,
        mode=mode,
        capped=capped,
        empty=not prepass_chunk_ids or not start_ids,
    )


def fuse_hybrid_chunk_ids(
    seed_chunk_ids: Sequence[str],
    expansion_chunk_ids: Sequence[str],
    traversal_chunk_ids: Sequence[str],
) -> HybridFusionResult:
    """Append-unique fuse seeds -> expansion -> extra traversal, keep-first dedupe.

    No re-ranking (FR-003d, research R6).
    """

    seen: set[str] = set()
    retrieved: list[str] = []
    seed_kept: list[str] = []
    expansion_added: list[str] = []
    traversal_added: list[str] = []

    for chunk_id in seed_chunk_ids:
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            retrieved.append(chunk_id)
            seed_kept.append(chunk_id)

    for chunk_id in expansion_chunk_ids:
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            retrieved.append(chunk_id)
            expansion_added.append(chunk_id)

    for chunk_id in traversal_chunk_ids:
        if chunk_id and chunk_id not in seen:
            seen.add(chunk_id)
            retrieved.append(chunk_id)
            traversal_added.append(chunk_id)

    return HybridFusionResult(
        retrieved_chunk_ids=tuple(retrieved),
        seed_count=len(seed_kept),
        expansion_added=tuple(expansion_added),
        traversal_added=tuple(traversal_added),
    )
