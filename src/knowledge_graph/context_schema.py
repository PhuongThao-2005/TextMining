from __future__ import annotations

from dataclasses import dataclass, field

from .overlay_schema import DocumentOverlay
from .traversal import TraversalPath, TraversalResult


@dataclass(frozen=True)
class GraphGuidedFilter:
    """Hard `id_str` filter passed to vector retrieval."""

    id_strs: tuple[str, ...]
    empty_filter_warning: bool
    filter_profile: str
    reason: str = ""


@dataclass(frozen=True)
class EvidenceContext:
    """Structured evidence bundle returned by the context builder."""

    filter: GraphGuidedFilter
    traversal: TraversalResult
    paths: tuple[TraversalPath, ...]
    documents: tuple[str, ...]
    overlays: tuple[DocumentOverlay, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

