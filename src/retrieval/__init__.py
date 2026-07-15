"""Vector embedding and retrieval module for the G-LRAG v2 dataset."""

from .config import VectorIndexConfig, VectorPaths
from .embeddings import HashingEmbedder, LazySentenceTransformerEmbedder, SentenceTransformerEmbedder
from .indexer import VectorIndexer
from .memory_utils import MemorySnapshot, print_memory, snapshot_memory
from .retriever import VectorRetriever
from .schema import RetrievalResult, RetrievedChunk
from .shard_loader import ShardLoader, LoadStats
from .stores import InMemoryVectorStore, QdrantVectorStore

__all__ = [
    "HashingEmbedder",
    "InMemoryVectorStore",
    "LazySentenceTransformerEmbedder",
    "LoadStats",
    "MemorySnapshot",
    "QdrantVectorStore",
    "RetrievalResult",
    "RetrievedChunk",
    "SentenceTransformerEmbedder",
    "ShardLoader",
    "VectorIndexer",
    "VectorIndexConfig",
    "VectorPaths",
    "VectorRetriever",
    "print_memory",
    "snapshot_memory",
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
