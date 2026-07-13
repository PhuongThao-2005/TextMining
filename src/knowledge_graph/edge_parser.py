from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from retrieval.io_utils import clean_text

from .edge_schema import GraphEdge
from .utils import as_bool, quality_flags


def parse_edge_row(row: dict[str, Any]) -> GraphEdge:
    """Parse a single `edges.jsonl` row into a canonical edge record.

    The parser preserves the upstream canonical direction and verification
    fields. It does not infer, flip, merge, or drop rows.
    """

    provenance = row.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}

    return GraphEdge(
        edge_id=clean_text(row.get("edge_id")),
        src_id=clean_text(row.get("src_id")),
        dst_id=clean_text(row.get("dst_id")),
        rel_canonical=clean_text(row.get("rel_canonical")),
        rel_group=clean_text(row.get("rel_group")),
        rel_raw=clean_text(row.get("rel_raw")),
        direction_normalized=as_bool(row.get("direction_normalized")),
        direction_verified=as_bool(row.get("direction_verified")),
        external_target=as_bool(row.get("external_target")),
        edge_quality_flags=quality_flags(row.get("edge_quality_flags")),
        provenance=dict(provenance),
    )


def parse_edge_rows(rows: Iterable[dict[str, Any]]) -> Iterator[GraphEdge]:
    """Parse a stream of edge rows."""

    for row in rows:
        yield parse_edge_row(row)


def verified_edge_rows(rows: Iterable[GraphEdge]) -> Iterator[GraphEdge]:
    """Yield only edges whose direction has been verified upstream.

    This is a read-only filter, not a repair step.
    """

    for edge in rows:
        if edge.direction_verified:
            yield edge
