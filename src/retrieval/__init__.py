"""Vector embedding and retrieval module for the G-LRAG v2 dataset."""

from .config import VectorIndexConfig, VectorPaths
from .embeddings import HashingEmbedder, SentenceTransformerEmbedder
from .indexer import VectorIndexer
from .retriever import VectorRetriever
from .schema import RetrievalResult, RetrievedChunk
from .shard_loader import ShardLoader, LoadStats
from .stores import InMemoryVectorStore, QdrantVectorStore

__all__ = [
    "HashingEmbedder",
    "InMemoryVectorStore",
    "LoadStats",
    "QdrantVectorStore",
    "RetrievalResult",
    "RetrievedChunk",
    "SentenceTransformerEmbedder",
    "ShardLoader",
    "VectorIndexer",
    "VectorIndexConfig",
    "VectorPaths",
    "VectorRetriever",
]

# FaissVectorStore is optional (requires faiss-cpu)
try:
    from .faiss_store import FaissVectorStore
    __all__.append("FaissVectorStore")
except RuntimeError:
    pass


# SQLitePayloadFaissVectorStore is optional (requires faiss-cpu + sqlite3 stdlib)
try:
    from .sqlite_faiss_store import SQLitePayloadFaissVectorStore
    __all__.append("SQLitePayloadFaissVectorStore")
except RuntimeError:
    pass

# BM25SparseRetriever is optional (requires rank_bm25)
try:
    from .sparse_retriever import BM25SparseRetriever
    __all__.append("BM25SparseRetriever")
except RuntimeError:
    pass

# HybridRetriever is optional (requires rank_bm25 + optionally sentence-transformers for CE)
try:
    from .hybrid_retriever import HybridRetriever, LatencyBreakdown
    __all__.extend(["HybridRetriever", "LatencyBreakdown"])
except (RuntimeError, ImportError):
    pass

# Colab-safe runtime helpers (feature 005) — pure policy/load-plan utilities
from .colab_runtime import (
    CleanupRequest,
    LoadPlan,
    MemorySnapshot,
    ResidentComponentSnapshot,
    RuntimeProfile,
    apply_cleanup,
    build_load_plan,
    capture_memory_snapshot,
    decide_graph_source_mode,
    format_load_plan,
    format_resident_snapshot,
    format_session_outcome,
    payload_cache_rebuild_warning,
    resolve_runtime_profile,
    session_outcome_label,
)
__all__.extend(
    [
        "CleanupRequest",
        "LoadPlan",
        "MemorySnapshot",
        "ResidentComponentSnapshot",
        "RuntimeProfile",
        "apply_cleanup",
        "build_load_plan",
        "capture_memory_snapshot",
        "decide_graph_source_mode",
        "format_load_plan",
        "format_resident_snapshot",
        "format_session_outcome",
        "payload_cache_rebuild_warning",
        "resolve_runtime_profile",
        "session_outcome_label",
    ]
)
