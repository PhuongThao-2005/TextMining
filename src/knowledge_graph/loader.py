from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from retrieval.io_utils import read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_V2_DATA_DIR = PROJECT_ROOT / "data" / "v2"


@dataclass(frozen=True)
class GraphLoaderPaths:
    """Filesystem contract for the v2 graph loader.

    The loader reads only the five source files required by the graph module
    bootstrap step. It does not touch provenance, overlay, or quarantine
    artifacts.
    """

    data_dir: Path = DEFAULT_V2_DATA_DIR
    documents_name: str = "documents.jsonl"
    provisions_name: str = "provisions.jsonl"
    chunks_name: str = "chunks.jsonl"
    edges_name: str = "edges.jsonl"
    external_stubs_name: str = "external_stubs.jsonl"

    @property
    def documents_path(self) -> Path:
        return self.data_dir / self.documents_name

    @property
    def provisions_path(self) -> Path:
        return self.data_dir / self.provisions_name

    @property
    def chunks_path(self) -> Path:
        return self.data_dir / self.chunks_name

    @property
    def edges_path(self) -> Path:
        return self.data_dir / self.edges_name

    @property
    def external_stubs_path(self) -> Path:
        return self.data_dir / self.external_stubs_name

    def required_paths(self) -> tuple[Path, ...]:
        """Return the five graph loader input paths in spec order."""

        return (
            self.documents_path,
            self.provisions_path,
            self.chunks_path,
            self.edges_path,
            self.external_stubs_path,
        )

    def validate(self) -> None:
        """Raise if any required v2 source file is missing."""

        missing = [path for path in self.required_paths() if not path.exists()]
        if missing:
            missing_list = ", ".join(str(path) for path in missing)
            raise FileNotFoundError(f"Missing graph loader inputs: {missing_list}")


@dataclass(frozen=True)
class GraphSourceBundle:
    """Container for the raw v2 graph source streams."""

    documents: Iterator[dict[str, Any]]
    provisions: Iterator[dict[str, Any]]
    chunks: Iterator[dict[str, Any]]
    edges: Iterator[dict[str, Any]]
    external_stubs: Iterator[dict[str, Any]]


def load_jsonl_records(path: Path) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from a JSONL file using the shared repository parser."""

    return read_jsonl(path)


def load_documents(path: Path) -> Iterator[dict[str, Any]]:
    """Load document records from `documents.jsonl`."""

    return load_jsonl_records(path)


def load_provisions(path: Path) -> Iterator[dict[str, Any]]:
    """Load provision records from `provisions.jsonl`."""

    return load_jsonl_records(path)


def load_chunks(path: Path) -> Iterator[dict[str, Any]]:
    """Load chunk records from `chunks.jsonl`."""

    return load_jsonl_records(path)


def load_edges(path: Path) -> Iterator[dict[str, Any]]:
    """Load edge records from `edges.jsonl`."""

    return load_jsonl_records(path)


def load_external_stubs(path: Path) -> Iterator[dict[str, Any]]:
    """Load external stub records from `external_stubs.jsonl`."""

    return load_jsonl_records(path)


class GraphLoader:
    """Load the v2 graph source files without constructing a graph.

    The loader is intentionally narrow: it reads only the five source files
    permitted for the graph bootstrap layer and returns raw JSON-decoded
    records.
    """

    def __init__(self, paths: GraphLoaderPaths | None = None) -> None:
        self.paths = paths or GraphLoaderPaths()

    def load_documents(self) -> Iterator[dict[str, Any]]:
        """Load document records."""

        self._ensure_exists(self.paths.documents_path)
        return load_documents(self.paths.documents_path)

    def load_provisions(self) -> Iterator[dict[str, Any]]:
        """Load provision records."""

        self._ensure_exists(self.paths.provisions_path)
        return load_provisions(self.paths.provisions_path)

    def load_chunks(self) -> Iterator[dict[str, Any]]:
        """Load chunk records."""

        self._ensure_exists(self.paths.chunks_path)
        return load_chunks(self.paths.chunks_path)

    def load_edges(self) -> Iterator[dict[str, Any]]:
        """Load edge records."""

        self._ensure_exists(self.paths.edges_path)
        return load_edges(self.paths.edges_path)

    def load_external_stubs(self) -> Iterator[dict[str, Any]]:
        """Load external stub records."""

        self._ensure_exists(self.paths.external_stubs_path)
        return load_external_stubs(self.paths.external_stubs_path)

    def load_all(self) -> GraphSourceBundle:
        """Load every graph source stream in one bundle.

        The returned bundle contains independent iterators for the five allowed
        v2 graph source files.
        """

        self.paths.validate()
        return GraphSourceBundle(
            documents=load_documents(self.paths.documents_path),
            provisions=load_provisions(self.paths.provisions_path),
            chunks=load_chunks(self.paths.chunks_path),
            edges=load_edges(self.paths.edges_path),
            external_stubs=load_external_stubs(self.paths.external_stubs_path),
        )

    @staticmethod
    def _ensure_exists(path: Path) -> None:
        """Raise a file-not-found error for a missing loader input."""

        if not path.exists():
            raise FileNotFoundError(f"Missing graph loader input: {path}")