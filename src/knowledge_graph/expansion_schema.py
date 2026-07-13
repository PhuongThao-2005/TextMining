from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExpansionStep:
    """One hop in a graph expansion walk."""

    src_id: str
    dst_id: str
    rel_type: str
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpansionResult:
    """Ordered expansion output for one or more seed chunk IDs."""

    seed_chunk_ids: tuple[str, ...]
    max_hop: int
    max_context: int | None
    expanded_node_ids: tuple[str, ...]
    traversed_edges: tuple[ExpansionStep, ...]
    ordered_context_chunks: tuple[str, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
