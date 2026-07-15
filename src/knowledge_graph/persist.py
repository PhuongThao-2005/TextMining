"""Portable structural knowledge-graph pickle persistence.

Serializes the in-memory ``KnowledgeGraph`` (nodes, edges, adjacency maps)
into a versioned envelope using the standard library ``pickle`` module.
Overlays are intentionally excluded; join them after load when needed.

Trust boundary: load only project-built ``.gpickle`` artifacts. Untrusted
pickles must not be unpickled. Colab/runtime must import compatible
``knowledge_graph`` class definitions (project ``src/`` on path or package).

No NetworkX dependency. No silent rebuild from JSONL on load.
"""

from __future__ import annotations

import os
import pickle
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .builder import GraphBuildStats, KnowledgeGraph

FORMAT_NAME = "g-lrag-knowledge-graph"
FORMAT_VERSION = 1
SUPPORTED_FORMAT_VERSIONS: frozenset[int] = frozenset({FORMAT_VERSION})


class GraphPickleError(Exception):
    """Base error for structural graph pickle save/load failures."""


class GraphPickleNotFoundError(GraphPickleError, FileNotFoundError):
    """Raised when the pickle path does not exist."""


class GraphPickleCorruptError(GraphPickleError):
    """Raised when the pickle file cannot be unpickled or is unreadable."""


class GraphPickleIncompatibleError(GraphPickleError):
    """Raised when the envelope format/version/payload is not supported."""


@dataclass(frozen=True)
class GraphPickleEnvelope:
    """Versioned on-disk envelope wrapping a structural ``KnowledgeGraph``."""

    format_name: str
    format_version: int
    created_at_utc: str
    source_data_dir: str | None
    stats: GraphBuildStats | dict[str, Any] | None
    warnings: tuple[str, ...]
    graph: KnowledgeGraph


@dataclass(frozen=True)
class GraphPickleArtifactInfo:
    """Metadata returned after a successful save."""

    path: Path
    format_version: int
    byte_size: int
    created_at_utc: str
    stats: GraphBuildStats | dict[str, Any] | None


@dataclass(frozen=True)
class GraphPickleLoadResult:
    """Restored structural graph plus envelope metadata from a pickle load.

    Overlays are never auto-joined. Callers that need currency/authority must
    join overlay sources explicitly after load.
    """

    graph: KnowledgeGraph
    format_version: int
    created_at_utc: str | None
    source_data_dir: str | None
    stats: GraphBuildStats | dict[str, Any] | None
    warnings: tuple[str, ...]
    path: Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def save_knowledge_graph(
    graph: KnowledgeGraph,
    path: Path | str,
    *,
    stats: GraphBuildStats | dict[str, Any] | None = None,
    warnings: tuple[str, ...] | list[str] = (),
    source_data_dir: str | None = None,
) -> GraphPickleArtifactInfo:
    """Serialize a structural ``KnowledgeGraph`` to a versioned ``.gpickle`` file.

    Writes via a same-directory temp file then ``os.replace`` so failed
    serialization does not leave a success-claimed final artifact. Creates
    parent directories when missing.

    Parameters
    ----------
    graph:
        Structural knowledge graph payload only (no overlays).
    path:
        Destination file path (configurable for Colab transfer workflows).
    stats:
        Optional build stats or core count dict for load-time smoke checks.
    warnings:
        Non-fatal build warnings snapshot.
    source_data_dir:
        Optional label of the v2 data directory used at build time.
    """
    if not isinstance(graph, KnowledgeGraph):
        raise TypeError(f"graph must be KnowledgeGraph, got {type(graph)!r}")

    output_path = Path(path)
    created_at_utc = _utc_now_iso()
    envelope = GraphPickleEnvelope(
        format_name=FORMAT_NAME,
        format_version=FORMAT_VERSION,
        created_at_utc=created_at_utc,
        source_data_dir=source_data_dir,
        stats=stats,
        warnings=tuple(warnings),
        graph=graph,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".gpickle.tmp",
            prefix=f".{output_path.name}.",
            dir=str(output_path.parent),
            delete=False,
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            pickle.dump(envelope, tmp_file, protocol=pickle.HIGHEST_PROTOCOL)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.replace(tmp_path, output_path)
        tmp_path = None
    except Exception:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    byte_size = output_path.stat().st_size
    return GraphPickleArtifactInfo(
        path=output_path.resolve(),
        format_version=FORMAT_VERSION,
        byte_size=byte_size,
        created_at_utc=created_at_utc,
        stats=stats,
    )


def load_knowledge_graph(path: Path | str) -> GraphPickleLoadResult:
    """Load a structural ``KnowledgeGraph`` from a trusted project pickle.

    Validates envelope ``format_name`` / ``format_version`` and payload type.
    Does **not** rebuild from JSONL and does **not** join overlays.

    Raises
    ------
    GraphPickleNotFoundError
        When the path is missing.
    GraphPickleCorruptError
        When the file is unreadable or not a valid pickle.
    GraphPickleIncompatibleError
        When the envelope format/version/payload is unsupported.
    """
    input_path = Path(path)
    if not input_path.exists():
        raise GraphPickleNotFoundError(
            f"Graph pickle not found: {input_path}. "
            "Provide a valid project-built .gpickle path; load does not rebuild from JSONL."
        )
    if not input_path.is_file():
        raise GraphPickleNotFoundError(
            f"Graph pickle path is not a file: {input_path}"
        )

    try:
        with input_path.open("rb") as handle:
            payload = pickle.load(handle)
    except GraphPickleError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface all unpickle failures clearly
        raise GraphPickleCorruptError(
            f"Unreadable or corrupt graph pickle at {input_path}: {exc}"
        ) from exc

    return _validate_and_wrap(payload, input_path)


def _validate_and_wrap(payload: Any, input_path: Path) -> GraphPickleLoadResult:
    """Validate unpickled payload and wrap as ``GraphPickleLoadResult``."""

    if isinstance(payload, GraphPickleEnvelope):
        format_name = payload.format_name
        format_version = payload.format_version
        created_at_utc = payload.created_at_utc
        source_data_dir = payload.source_data_dir
        stats = payload.stats
        warnings = tuple(payload.warnings or ())
        graph = payload.graph
    elif isinstance(payload, dict):
        # Defensive path for future dict-shaped envelopes; still validate strictly.
        format_name = payload.get("format_name")
        format_version = payload.get("format_version")
        created_at_utc = payload.get("created_at_utc")
        source_data_dir = payload.get("source_data_dir")
        stats = payload.get("stats")
        warnings = tuple(payload.get("warnings") or ())
        graph = payload.get("graph")
    else:
        raise GraphPickleIncompatibleError(
            f"Incompatible graph pickle at {input_path}: "
            f"expected GraphPickleEnvelope, got {type(payload).__name__}. "
            "Rebuild the artifact with the project save path."
        )

    if format_name != FORMAT_NAME:
        raise GraphPickleIncompatibleError(
            f"Incompatible graph pickle at {input_path}: "
            f"format_name={format_name!r}, expected {FORMAT_NAME!r}."
        )

    if not isinstance(format_version, int) or format_version not in SUPPORTED_FORMAT_VERSIONS:
        raise GraphPickleIncompatibleError(
            f"Incompatible graph pickle at {input_path}: "
            f"format_version={format_version!r}, supported={sorted(SUPPORTED_FORMAT_VERSIONS)}."
        )

    if not isinstance(graph, KnowledgeGraph):
        raise GraphPickleIncompatibleError(
            f"Incompatible graph pickle at {input_path}: "
            f"payload graph must be KnowledgeGraph, got {type(graph).__name__}."
        )

    return GraphPickleLoadResult(
        graph=graph,
        format_version=format_version,
        created_at_utc=created_at_utc,
        source_data_dir=source_data_dir,
        stats=stats,
        warnings=warnings,
        path=input_path.resolve(),
    )
