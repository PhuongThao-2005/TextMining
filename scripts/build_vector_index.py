#!/usr/bin/env python3
"""Build the v2 vector index for G-LRAG."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from retrieval import (  # noqa: E402
    HashingEmbedder,
    InMemoryVectorStore,
    QdrantVectorStore,
    SentenceTransformerEmbedder,
    VectorIndexer,
)
from retrieval.config import DEFAULT_DATA_DIR, VectorIndexConfig, VectorPaths  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build vector embeddings and retrieval index.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--chunks-name", default="chunks.jsonl" if (DEFAULT_DATA_DIR / "chunks.jsonl").exists() else "chunks-003.jsonl")
    parser.add_argument("--model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test limit.")
    parser.add_argument("--store", choices=["qdrant", "memory"], default="qdrant")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--dev-hashing", action="store_true", help="Use deterministic local embeddings.")
    args = parser.parse_args()

    paths = VectorPaths(
        data_dir=args.data_dir,
        output_dir=args.out_dir or args.data_dir / "vector_retrieval",
        chunks_name=args.chunks_name,
    )
    config = VectorIndexConfig(embedding_model=args.model, batch_size=args.batch_size)
    embedder = (
        HashingEmbedder()
        if args.dev_hashing
        else SentenceTransformerEmbedder(
            args.model,
            query_prefix=config.query_prefix,
            passage_prefix=config.passage_prefix,
        )
    )
    store = InMemoryVectorStore() if args.store == "memory" else QdrantVectorStore(config.collection_name, args.qdrant_url)
    stats = VectorIndexer(paths=paths, config=config, embedder=embedder, store=store).build(limit=args.limit)
    print(f"Indexed {stats.total_chunks_indexed:,}/{stats.total_chunks_in_source:,} chunks.")
    print(f"Report: {paths.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
