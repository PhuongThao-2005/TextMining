"""Build the vector database from pre-computed embedding shards and run sample retrieval tests.

Usage (from project root):
    python -m src.retrieval.build_vector_db \\
        --embedding-dir ../embedding \\
        --data-dir data/v2 \\
        --store qdrant            # or 'memory' for local testing
        --limit 10000             # optional: only load first N records

For local smoke testing without Qdrant:
    python -m src.retrieval.build_vector_db \\
        --embedding-dir ../embedding \\
        --store memory \\
        --limit 5000
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build vector DB from embedding shards and run sample retrieval tests.",
    )
    parser.add_argument(
        "--embedding-dir",
        type=Path,
        required=True,
        help="Directory containing vector_shards_part_XX/ directories",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to data/v2 directory (for quarantine/external_stubs filtering). "
             "If not provided, quarantine filtering is skipped.",
    )
    parser.add_argument(
        "--store",
        choices=["qdrant", "memory", "faiss"],
        default="faiss",
        help="Vector store backend: 'faiss' (recommended, saves to disk), 'qdrant' (Docker), or 'memory' (RAM only)",
    )
    parser.add_argument(
        "--qdrant-url",
        default="http://localhost:6333",
        help="Qdrant server URL (only used with --store qdrant)",
    )
    parser.add_argument(
        "--collection",
        default="legal_chunks",
        help="Qdrant collection name",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max records to load (for testing). Default: load all.",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=None,
        help="Directory to save/load FAISS index (only used with --store faiss). "
             "Default: embedding_dir/faiss_index",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Upsert batch size",
    )
    parser.add_argument(
        "--no-recreate",
        action="store_true",
        help="Do NOT recreate collection (append to existing)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip sample retrieval tests",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory to write the vector_index_report.md. Default: embedding_dir.",
    )
    return parser.parse_args()


def create_store(args: argparse.Namespace):
    """Create the appropriate VectorStore based on CLI args."""
    from .stores import InMemoryVectorStore, QdrantVectorStore

    if args.store == "faiss":
        from .faiss_store import FaissVectorStore
        index_dir = args.index_dir or (args.embedding_dir / "faiss_index")
        logger.info("Using FaissVectorStore at %s", index_dir)
        return FaissVectorStore.create(dimension=1024, index_dir=index_dir)
    elif args.store == "qdrant":
        logger.info("Connecting to Qdrant at %s", args.qdrant_url)
        return QdrantVectorStore(
            collection_name=args.collection,
            url=args.qdrant_url,
        )
    else:
        logger.info("Using InMemoryVectorStore (local testing mode)")
        return InMemoryVectorStore()


def create_embedder():
    """Create the embedder for query encoding during sample tests."""
    from .embeddings import SentenceTransformerEmbedder

    try:
        return SentenceTransformerEmbedder(
            model_name="intfloat/multilingual-e5-large",
            query_prefix="query: ",
            passage_prefix="passage: ",
        )
    except RuntimeError:
        logger.warning(
            "SentenceTransformerEmbedder not available, using HashingEmbedder for tests"
        )
        from .embeddings import HashingEmbedder
        return HashingEmbedder(dimension=1024)


# ---------------------------------------------------------------------------
# Sample retrieval tests (Spec §5, §9)
# ---------------------------------------------------------------------------

SAMPLE_QUERIES = [
    {
        "query": "Quyền sở hữu trí tuệ theo pháp luật Việt Nam",
        "description": "Sở hữu trí tuệ — luật chuyên ngành",
    },
    {
        "query": "Điều kiện thành lập doanh nghiệp",
        "description": "Luật doanh nghiệp — điều kiện thành lập",
    },
    {
        "query": "Quy định về thuế thu nhập cá nhân",
        "description": "Thuế TNCN — luật thuế",
    },
    {
        "query": "Trách nhiệm bồi thường thiệt hại ngoài hợp đồng",
        "description": "Bộ luật dân sự — bồi thường thiệt hại",
    },
    {
        "query": "Quyền và nghĩa vụ của người lao động",
        "description": "Bộ luật lao động — quyền NLĐ",
    },
    {
        "query": "Xử phạt vi phạm hành chính trong lĩnh vực môi trường",
        "description": "Xử phạt VPHC — môi trường",
    },
    {
        "query": "Thủ tục đăng ký kết hôn",
        "description": "Luật hôn nhân gia đình — thủ tục ĐKKH",
    },
    {
        "query": "Quy định về bảo vệ quyền lợi người tiêu dùng",
        "description": "Luật bảo vệ NTD",
    },
    {
        "query": "Thẩm quyền giải quyết tranh chấp đất đai",
        "description": "Luật đất đai — thẩm quyền",
    },
    {
        "query": "Quy định về an toàn thực phẩm",
        "description": "An toàn thực phẩm",
    },
]


def run_sample_tests(store, embedder, config) -> list[dict]:
    """Run sample retrieval queries and return results for the report."""
    from .retriever import VectorRetriever

    retriever = VectorRetriever(config=config, embedder=embedder, store=store)
    results = []

    for i, test_case in enumerate(SAMPLE_QUERIES, 1):
        query = test_case["query"]
        desc = test_case["description"]
        logger.info("Sample test %d/%d: %s", i, len(SAMPLE_QUERIES), desc)

        try:
            result = retriever.retrieve(
                query=query,
                filter_profile="broad",  # Use broad to see all results
                top_k=20,
                top_n=5,
                score_threshold=0.0,  # Accept all scores for testing
            )

            test_result = {
                "query": query,
                "description": desc,
                "total_candidates": result.total_candidates,
                "returned_chunks": len(result.chunks),
                "filter_profile": result.filter_profile_used,
                "top_chunks": [],
            }

            for chunk in result.chunks[:5]:
                test_result["top_chunks"].append({
                    "chunk_id": chunk.chunk_id,
                    "title": chunk.title[:80] if chunk.title else "",
                    "citation_anchor": chunk.citation_anchor[:100] if chunk.citation_anchor else "",
                    "unit_type": chunk.unit_type,
                    "validity_group": chunk.validity_group,
                    "vector_score": round(chunk.vector_score, 4),
                    "rerank_score": round(chunk.rerank_score, 4),
                    "chunk_text_preview": (chunk.chunk_text[:150] + "...") if len(chunk.chunk_text) > 150 else chunk.chunk_text,
                })

            results.append(test_result)

        except Exception as exc:
            logger.error("Test %d failed: %s", i, exc)
            results.append({
                "query": query,
                "description": desc,
                "error": str(exc),
            })

    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_report(
    stats,
    test_results: list[dict],
    report_path: Path,
    store_type: str,
    embedder_model: str,
) -> None:
    """Write vector_index_report.md with load stats and sample test results."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Vector Index Report",
        "",
        "## Load Statistics",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| store_type | `{store_type}` |",
        f"| embedding_model | `{embedder_model}` |",
        f"| total_shards | {stats.total_shards} |",
        f"| total_records_loaded | {stats.total_records_loaded:,} |",
        f"| total_records_skipped | {stats.total_records_skipped:,} |",
        f"| duplicate_chunk_ids | {stats.duplicate_chunk_ids} |",
        f"| quarantine_filtered | {stats.quarantine_filtered} |",
        f"| external_stub_filtered | {stats.external_stub_filtered} |",
        f"| missing_chunk_text | {stats.missing_chunk_text} |",
        f"| missing_citation_anchor | {stats.missing_citation_anchor} |",
        f"| elapsed_seconds | {stats.elapsed_seconds:.2f} |",
        "",
        "## Acceptance Checks",
        "",
        f"- `total_records_loaded > 0`: {stats.total_records_loaded > 0}",
        f"- `duplicate_chunk_ids == 0`: {stats.duplicate_chunk_ids == 0}",
        f"- `missing_chunk_text == 0`: {stats.missing_chunk_text == 0}",
        f"- `missing_citation_anchor == 0`: {stats.missing_citation_anchor == 0}",
        f"- `quarantine/stubs filtered`: {stats.quarantine_filtered + stats.external_stub_filtered} chunks removed",
        "",
    ]

    if stats.errors:
        lines.extend([
            "## Errors",
            "",
        ])
        for error in stats.errors:
            lines.append(f"- {error}")
        lines.append("")

    if test_results:
        lines.extend([
            "## Sample Retrieval Tests",
            "",
        ])
        for i, test in enumerate(test_results, 1):
            lines.append(f"### Test {i}: {test.get('description', 'N/A')}")
            lines.append("")
            lines.append(f"**Query:** {test.get('query', 'N/A')}")
            lines.append("")

            if "error" in test:
                lines.append(f"**Error:** {test['error']}")
                lines.append("")
                continue

            lines.append(f"- Candidates: {test.get('total_candidates', 0)}")
            lines.append(f"- Returned: {test.get('returned_chunks', 0)}")
            lines.append(f"- Filter: `{test.get('filter_profile', 'N/A')}`")
            lines.append("")

            top_chunks = test.get("top_chunks", [])
            if top_chunks:
                lines.append("| # | Score | Rerank | Title | Unit | Validity |")
                lines.append("| --- | --- | --- | --- | --- | --- |")
                for j, chunk in enumerate(top_chunks, 1):
                    title = chunk.get("title", "")[:50]
                    lines.append(
                        f"| {j} | {chunk.get('vector_score', 0):.4f} "
                        f"| {chunk.get('rerank_score', 0):.4f} "
                        f"| {title} "
                        f"| {chunk.get('unit_type', '')} "
                        f"| {chunk.get('validity_group', '')} |"
                    )
                lines.append("")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Report written to %s", report_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Validate paths
    if not args.embedding_dir.exists():
        logger.error("Embedding directory not found: %s", args.embedding_dir)
        sys.exit(1)

    # Create store
    store = create_store(args)

    # Load shards
    from .shard_loader import ShardLoader

    loader = ShardLoader(
        store=store,
        embedding_dir=args.embedding_dir,
        upsert_batch_size=args.batch_size,
    )

    logger.info("Starting shard loading...")
    stats = loader.load_all(
        recreate=not args.no_recreate,
        data_dir=args.data_dir,
        limit=args.limit,
    )

    logger.info(
        "Loading complete: %d records loaded, %d skipped in %.1fs",
        stats.total_records_loaded,
        stats.total_records_skipped,
        stats.elapsed_seconds,
    )

    # Save FAISS index if applicable
    if args.store == "faiss" and hasattr(store, "save"):
        logger.info("Saving FAISS index to disk...")
        store.save()
        logger.info("FAISS index saved: %d vectors", store.total_vectors)

    # Run sample tests
    test_results = []
    if not args.skip_tests and stats.total_records_loaded > 0:
        logger.info("Running sample retrieval tests...")
        from .config import VectorIndexConfig
        config = VectorIndexConfig(collection_name=args.collection)
        embedder = create_embedder()
        test_results = run_sample_tests(store, embedder, config)
        logger.info("Sample tests complete: %d tests run", len(test_results))

    # Write report
    report_dir = args.report_dir or args.embedding_dir
    report_path = report_dir / "vector_index_report.md"
    write_report(
        stats=stats,
        test_results=test_results,
        report_path=report_path,
        store_type=args.store,
        embedder_model="intfloat/multilingual-e5-large",
    )

    # Summary
    print("\n" + "=" * 60)
    print("VECTOR DB BUILD COMPLETE")
    print(f"  Records loaded:  {stats.total_records_loaded:,}")
    print(f"  Records skipped: {stats.total_records_skipped:,}")
    print(f"  Quarantine:      {stats.quarantine_filtered}")
    print(f"  External stubs:  {stats.external_stub_filtered}")
    print(f"  Elapsed:         {stats.elapsed_seconds:.1f}s")
    print(f"  Report:          {report_path}")
    if test_results:
        passed = sum(1 for t in test_results if "error" not in t)
        print(f"  Tests:           {passed}/{len(test_results)} passed")
    print("=" * 60)


if __name__ == "__main__":
    main()
