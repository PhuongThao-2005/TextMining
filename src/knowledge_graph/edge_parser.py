from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from retrieval.io_utils import clean_text

from .edge_schema import GraphEdge


def _as_bool(value: Any, default: bool = False) -> bool:
    """Convert a JSON value to bool with a stable default."""

    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _quality_flags(values: Any) -> tuple[str, ...]:
    """Normalize a JSON list of edge quality flags into an immutable tuple."""

    if not values:
        return ()
    return tuple(clean_text(item) for item in values if clean_text(item))


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
        direction_normalized=_as_bool(row.get("direction_normalized")),
        direction_verified=_as_bool(row.get("direction_verified")),
        external_target=_as_bool(row.get("external_target")),
        edge_quality_flags=_quality_flags(row.get("edge_quality_flags")),
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
