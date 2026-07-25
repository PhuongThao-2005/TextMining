#!/usr/bin/env python3
"""Build a BM25 sparse index from chunks.jsonl for hybrid retrieval.

Reads chunks from the project data directory, tokenizes using the best
available Vietnamese tokenizer, builds a BM25Okapi index, and persists
it to ``data/sparse_index/``.

Usage::

    python scripts/build_sparse_index.py
    python scripts/build_sparse_index.py --chunks-path data/v2/chunks.jsonl --output-dir data/sparse_index
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from retrieval.config import DEFAULT_DATA_DIR  # noqa: E402
from retrieval.sparse_retriever import BM25SparseRetriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BM25 sparse index from chunks.jsonl")
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=None,
        help="Path to chunks.jsonl. Defaults to auto-detect from project data dir.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "sparse_index",
        help="Directory to save the BM25 index files.",
    )
    parser.add_argument(
        "--text-field",
        default="chunk_text",
        help="JSON field name for chunk text (default: chunk_text).",
    )
    parser.add_argument(
        "--id-field",
        default="chunk_id",
        help="JSON field name for chunk ID (default: chunk_id).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Auto-detect chunks path
    if args.chunks_path is None:
        candidates = [
            DEFAULT_DATA_DIR / "chunks.jsonl",
            DEFAULT_DATA_DIR / "chunks-003.jsonl",
            PROJECT_ROOT / "data" / "v2" / "chunks.jsonl",
            PROJECT_ROOT / "data" / "pre-processed" / "chunks.jsonl",
        ]
        for path in candidates:
            if path.exists():
                args.chunks_path = path
                break
        if args.chunks_path is None:
            print("ERROR: Could not find chunks.jsonl. Tried:", file=sys.stderr)
            for p in candidates:
                print(f"  {p}", file=sys.stderr)
            return 1

    print(f"Chunks path: {args.chunks_path}")
    print(f"Output dir:  {args.output_dir}")
    print(f"Text field:  {args.text_field}")
    print(f"ID field:    {args.id_field}")

    t0 = time.perf_counter()

    retriever = BM25SparseRetriever.build_from_chunks(
        args.chunks_path,
        text_field=args.text_field,
        id_field=args.id_field,
    )

    build_time = time.perf_counter() - t0
    print(f"\nBM25 index built: {retriever.total_documents:,} documents in {build_time:.2f}s")

    retriever.save(args.output_dir)

    # Quick smoke test
    print("\n--- Smoke test ---")
    test_query = "Điều kiện lao động"
    hits, search_time = retriever.search_with_latency(test_query, top_k=5)
    print(f"Query: '{test_query}'")
    print(f"Search time: {search_time:.4f}s")
    print(f"Results: {len(hits)}")
    for rank, hit in enumerate(hits, start=1):
        chunk_id = hit.payload.get("chunk_id") or hit.point_id
        text_preview = str(hit.payload.get("chunk_text") or "")[:100]
        print(f"  [{rank}] score={hit.score:.4f} chunk_id={chunk_id}")
        print(f"       {text_preview}...")

    print(f"\nDone. Index saved to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
