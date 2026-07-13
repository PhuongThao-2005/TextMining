from __future__ import annotations

from dataclasses import dataclass

from retrieval import HashingEmbedder, QdrantVectorStore, SentenceTransformerEmbedder, VectorIndexConfig, VectorRetriever


@dataclass(frozen=True)
class RetrieverRuntimeConfig:
    store: str = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    collection_name: str = "legal_chunks"
    model: str = "intfloat/multilingual-e5-large"
    dev_hashing: bool = False
    top_k: int = 30
    top_n: int = 10
    score_threshold: float | None = 0.3
    expand_units: bool = True


def build_vector_retriever(runtime: RetrieverRuntimeConfig) -> VectorRetriever:
    config = VectorIndexConfig(
        collection_name=runtime.collection_name,
        embedding_model=runtime.model,
        top_k=runtime.top_k,
        top_n=runtime.top_n,
        score_threshold=0.0 if runtime.score_threshold is None else runtime.score_threshold,
        expand_units=runtime.expand_units,
    )
    embedder = (
        HashingEmbedder()
        if runtime.dev_hashing
        else SentenceTransformerEmbedder(runtime.model, query_prefix=config.query_prefix, passage_prefix=config.passage_prefix)
    )
    if runtime.store != "qdrant":
        raise ValueError("Evaluation CLI currently expects a prebuilt Qdrant index; use --dev-hashing only with tests.")
    store = QdrantVectorStore(runtime.collection_name, runtime.qdrant_url, runtime.qdrant_api_key)
    return VectorRetriever(config=config, embedder=embedder, store=store)

