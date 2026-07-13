from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphEdge:
    """Canonical cross-document edge record from `edges.jsonl`."""

    edge_id: str
    src_id: str
    dst_id: str
    rel_canonical: str
    rel_group: str
    rel_raw: str
    direction_normalized: bool
    direction_verified: bool
    external_target: bool
    edge_quality_flags: tuple[str, ...]
    provenance: dict[str, Any]

