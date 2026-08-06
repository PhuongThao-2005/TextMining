from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from retrieval import (
    HashingEmbedder,
    QdrantVectorStore,
    SentenceTransformerEmbedder,
    SQLitePayloadFaissVectorStore,
    VectorIndexConfig,
    VectorRetriever,
)


@dataclass(frozen=True)
class RetrieverRuntimeConfig:
    store: Literal["faiss", "qdrant"] = "faiss"
    index_dir: str | Path = "data/faiss_index"
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

    if runtime.dev_hashing:
        # Smoke-test path: in-memory store, no real index required (FR-011/FR-012 n/a here).
        from retrieval import InMemoryVectorStore

        store = InMemoryVectorStore()
    elif runtime.store == "faiss":
        index_dir = Path(runtime.index_dir)
        try:
            store = SQLitePayloadFaissVectorStore.load(index_dir)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Could not construct a FAISS-backed vector retriever from index_dir={index_dir!s}: {exc}. "
                "Ensure INDEX_DIR points at a directory containing 'index.faiss' and 'payloads.jsonl' "
                "(see scripts/build_vector_index.py)."
            ) from exc
    elif runtime.store == "qdrant":
        store = QdrantVectorStore(runtime.collection_name, runtime.qdrant_url, runtime.qdrant_api_key)
    else:
        raise ValueError(f"Unknown runtime.store={runtime.store!r}; expected 'faiss' or 'qdrant'.")

    embedder_dimension = getattr(embedder, "dimension", None)
    store_dimension = getattr(store, "dimension", None)
    if (
        isinstance(embedder_dimension, int)
        and isinstance(store_dimension, int)
        and embedder_dimension != store_dimension
    ):
        raise ValueError(
            "Embedding/index dimension mismatch before retrieval: "
            f"embedder={embedder_dimension}, index={store_dimension}."
        )

    return VectorRetriever(config=config, embedder=embedder, store=store)

