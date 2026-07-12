"""Vector embedding and retrieval module for the G-LRAG v2 dataset."""

from .config import VectorIndexConfig, VectorPaths
from .embeddings import HashingEmbedder, SentenceTransformerEmbedder
from .indexer import VectorIndexer
from .retriever import VectorRetriever
from .schema import RetrievalResult, RetrievedChunk
from .stores import InMemoryVectorStore, QdrantVectorStore

__all__ = [
    "HashingEmbedder",
    "InMemoryVectorStore",
    "QdrantVectorStore",
    "RetrievalResult",
    "RetrievedChunk",
    "SentenceTransformerEmbedder",
    "VectorIndexer",
    "VectorIndexConfig",
    "VectorPaths",
    "VectorRetriever",
]
