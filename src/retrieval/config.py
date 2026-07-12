from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = (
    PROJECT_ROOT / "data" / "v2"
    if (PROJECT_ROOT / "data" / "v2").exists()
    else PROJECT_ROOT / "data" / "pre-processed"
)


@dataclass(frozen=True)
class VectorPaths:
    """Filesystem contract for the v2 vector retrieval stage."""

    data_dir: Path = DEFAULT_DATA_DIR
    output_dir: Path = DEFAULT_DATA_DIR / "vector_retrieval"
    chunks_name: str = "chunks.jsonl" if (DEFAULT_DATA_DIR / "chunks.jsonl").exists() else "chunks-003.jsonl"
    provisions_name: str = "provisions.jsonl"
    documents_name: str = "documents.jsonl"
    text_provenance_name: str = "text_provenance.jsonl"

    @property
    def chunks_path(self) -> Path:
        return self.data_dir / self.chunks_name

    @property
    def provisions_path(self) -> Path:
        return self.data_dir / self.provisions_name

    @property
    def documents_path(self) -> Path:
        return self.data_dir / self.documents_name

    @property
    def text_provenance_path(self) -> Path:
        return self.data_dir / self.text_provenance_name

    @property
    def report_path(self) -> Path:
        return self.output_dir / "vector_index_report.md"


@dataclass(frozen=True)
class VectorIndexConfig:
    """Runtime configuration for embedding, indexing, and retrieval."""

    collection_name: str = "legal_chunks"
    embedding_model: str = "intfloat/multilingual-e5-large"
    retrieval_text_template_version: str = "v2.identity_header_plus_chunk_text.1"
    batch_size: int = 32
    distance: str = "cosine"
    score_threshold: float = 0.3
    top_k: int = 20
    top_n: int = 10
    expand_units: bool = True
    max_expansion_chunks: int = 3
    hnsw_m: int = 16
    hnsw_ef_construction: int = 100
    query_prefix: str = "query: "
    passage_prefix: str = "passage: "
