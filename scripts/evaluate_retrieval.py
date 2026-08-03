#!/usr/bin/env python3
"""Run retrieval-only evaluation on a frozen QA benchmark."""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.io_utils import qa_id, read_jsonl, write_json, write_jsonl  # noqa: E402
from evaluation.metrics import aggregate, aggregate_by, hit_at_k, jaccard_at_k, mrr_at_k, ndcg_at_k, recall_at_k  # noqa: E402
from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever  # noqa: E402
from retrieval.embeddings import SentenceTransformerEmbedder  # noqa: E402
from retrieval.sqlite_faiss_store import SQLitePayloadFaissVectorStore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate chunk retrieval with Recall@k, MRR, nDCG, and Jaccard.")
    parser.add_argument("--qa-path", type=Path, required=True, help="Frozen QA JSONL, e.g. qa_final.jsonl.")
    parser.add_argument("--out-dir", type=Path, default=Path("evaluation_runs/retrieval"))
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--store", choices=["faiss", "qdrant"], default="faiss")
    parser.add_argument("--index-dir", type=Path, default=Path("data/faiss_index"))
    parser.add_argument(
        "--raw-faiss",
        action="store_true",
        help="Bypass VectorRetriever and evaluate direct FAISS search like dense-embedding-ablation.ipynb.",
    )
    parser.add_argument(
        "--runtime-index-dir",
        type=Path,
        default=None,
        help=(
            "Optional writable FAISS mirror directory. Useful on Kaggle because "
            "/kaggle/input is read-only and the SQLite payload cache may need refresh."
        ),
    )
    parser.add_argument("--filter-profile", default="broad", choices=["current_law", "broad", "historical"])
    parser.add_argument("--collection", default="legal_chunks")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--qdrant-api-key", default=None)
    parser.add_argument("--model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--score-threshold", type=float, default=0.3)
    parser.add_argument("--no-expand-units", action="store_true")
    parser.add_argument(
        "--include-empty-ground-truth",
        action="store_true",
        help=(
            "Include rows with no ground_truth.chunk_ids in the case output and counts. "
            "Retrieval metrics for those rows are null and excluded from metric averages."
        ),
    )
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test on first N evaluated QA.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_k = max(args.top_k)
    runtime_index_dir = (
        prepare_writable_index_dir(args.index_dir, args.runtime_index_dir)
        if args.store == "faiss" and args.runtime_index_dir is not None
        else args.index_dir
    )
    if args.raw_faiss:
        if args.store != "faiss":
            raise ValueError("--raw-faiss requires --store faiss")
        store = SQLitePayloadFaissVectorStore.load(runtime_index_dir)
        embedder = SentenceTransformerEmbedder(args.model)
        retriever = None
    else:
        store = None
        embedder = None
        retriever = build_vector_retriever(
            RetrieverRuntimeConfig(
                store=args.store,
                index_dir=runtime_index_dir,
                qdrant_url=args.qdrant_url,
                qdrant_api_key=args.qdrant_api_key,
                collection_name=args.collection,
                model=args.model,
                top_k=max(max_k * 3, 30),
                top_n=max_k,
                score_threshold=args.score_threshold,
                expand_units=not args.no_expand_units,
            )
        )

    cases: list[dict[str, Any]] = []
    skipped_unanswerable = 0
    skipped_missing_gt = 0
    evaluated_empty_gt = 0
    total_rows_seen = 0
    for index, qa in enumerate(read_jsonl(args.qa_path), start=1):
        total_rows_seen += 1
        is_unanswerable = (
            str(qa.get("answer_type") or "").lower() == "unanswerable"
            or str(qa.get("category") or "").lower() == "unanswerable"
        )
        if is_unanswerable and not args.include_empty_ground_truth:
            skipped_unanswerable += 1
            continue
        gt = qa.get("ground_truth") or {}
        relevant = {str(chunk_id) for chunk_id in gt.get("chunk_ids") or [] if chunk_id}
        if not relevant and not args.include_empty_ground_truth:
            skipped_missing_gt += 1
            continue
        if not relevant:
            evaluated_empty_gt += 1
        if args.limit is not None and len(cases) >= args.limit:
            break

        question = str(qa.get("question") or "")
        if args.raw_faiss:
            assert store is not None and embedder is not None
            query_vector = embedder.encode_queries([question])[0]
            hits = store.search(query_vector, limit=max_k, score_threshold=None, filters=None)
            retrieved_ids = [str(hit.payload.get("chunk_id") or hit.point_id) for hit in hits]
            retrieved_rows = [
                {
                    "rank": rank,
                    "chunk_id": str(hit.payload.get("chunk_id") or hit.point_id),
                    "document_id": hit.payload.get("id_str"),
                    "provision_id": hit.payload.get("parent_unit_id"),
                    "rerank_score": None,
                    "vector_score": hit.score,
                    "citation": hit.payload.get("citation_anchor") or hit.payload.get("citation_label"),
                }
                for rank, hit in enumerate(hits, start=1)
            ]
        else:
            assert retriever is not None
            result = retriever.retrieve(question, filter_profile=args.filter_profile, top_n=max_k)
            retrieved_ids = [chunk.chunk_id for chunk in result.chunks]
            retrieved_rows = [
                {
                    "rank": rank,
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.id_str,
                    "provision_id": chunk.parent_unit_id,
                    "rerank_score": chunk.rerank_score,
                    "vector_score": chunk.vector_score,
                    "citation": chunk.citation_anchor or chunk.citation_label,
                }
                for rank, chunk in enumerate(result.chunks, start=1)
            ]
        row: dict[str, Any] = {
            "qa_id": qa_id(qa, index),
            "question": question,
            "category": qa.get("category"),
            "difficulty": qa.get("difficulty"),
            "answer_type": qa.get("answer_type"),
            "ground_truth_chunk_ids": sorted(relevant),
            "empty_ground_truth": not bool(relevant),
            "retrieved_chunk_ids": retrieved_ids,
            "retrieved": retrieved_rows,
        }
        for k in args.top_k:
            if relevant:
                row[f"recall@{k}"] = recall_at_k(retrieved_ids, relevant, k)
                row[f"hit@{k}"] = hit_at_k(retrieved_ids, relevant, k)
                row[f"mrr@{k}"] = mrr_at_k(retrieved_ids, relevant, k)
                row[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, relevant, k)
                row[f"jaccard@{k}"] = jaccard_at_k(retrieved_ids, relevant, k)
            else:
                row[f"recall@{k}"] = None
                row[f"hit@{k}"] = None
                row[f"mrr@{k}"] = None
                row[f"ndcg@{k}"] = None
                row[f"jaccard@{k}"] = None
        cases.append(row)
        if len(cases) % 25 == 0:
            print(f"Evaluated {len(cases)} retrieval cases...")

    metric_keys = [f"{name}@{k}" for k in args.top_k for name in ("recall", "hit", "mrr", "ndcg", "jaccard")]
    summary = {
        "qa_path": str(args.qa_path),
        "retriever": {
            "store": args.store,
            "raw_faiss": args.raw_faiss,
            "source_index_dir": str(args.index_dir),
            "runtime_index_dir": str(runtime_index_dir),
            "collection": args.collection,
            "qdrant_url": args.qdrant_url,
            "model": args.model,
            "filter_profile": args.filter_profile,
            "score_threshold": args.score_threshold,
            "expand_units": not args.no_expand_units,
            "candidate_top_k": max(max_k * 3, 30),
            "final_top_n": max_k,
            "top_k": args.top_k,
            "include_empty_ground_truth": args.include_empty_ground_truth,
        },
        "counts": {
            "total_rows_seen": total_rows_seen,
            "evaluated": len(cases),
            "evaluated_empty_ground_truth": evaluated_empty_gt,
            "skipped_unanswerable": skipped_unanswerable,
            "skipped_missing_ground_truth_chunks": skipped_missing_gt,
        },
        "overall": aggregate(cases, metric_keys),
        "by_category": aggregate_by(cases, "category", metric_keys),
        "by_difficulty": aggregate_by(cases, "difficulty", metric_keys),
        "by_answer_type": aggregate_by(cases, "answer_type", metric_keys),
    }
    write_jsonl(args.out_dir / "retrieval_cases.jsonl", cases)
    write_json(args.out_dir / "retrieval_metrics.json", summary)
    write_report(args.out_dir / "retrieval_report.md", summary, metric_keys)
    print(f"Retrieval cases: {args.out_dir / 'retrieval_cases.jsonl'}")
    print(f"Retrieval metrics: {args.out_dir / 'retrieval_metrics.json'}")
    return 0


def write_report(path: Path, summary: dict[str, Any], metric_keys: list[str]) -> None:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"- QA path: `{summary['qa_path']}`",
        f"- Store: `{summary['retriever']['store']}`",
        f"- Raw FAISS: {summary['retriever']['raw_faiss']}",
        f"- Source index dir: `{summary['retriever']['source_index_dir']}`",
        f"- Runtime index dir: `{summary['retriever']['runtime_index_dir']}`",
        f"- Final contexts: {summary['retriever']['final_top_n']}",
        f"- Candidate top-k: {summary['retriever']['candidate_top_k']}",
        f"- Include empty ground truth: {summary['retriever']['include_empty_ground_truth']}",
        f"- Total rows seen: {summary['counts']['total_rows_seen']}",
        f"- Evaluated QA: {summary['counts']['evaluated']}",
        f"- Evaluated empty-GT QA: {summary['counts']['evaluated_empty_ground_truth']}",
        f"- Skipped unanswerable QA: {summary['counts']['skipped_unanswerable']}",
        f"- Skipped missing GT chunks: {summary['counts']['skipped_missing_ground_truth_chunks']}",
        "- Metric averages exclude rows where that metric is not applicable.",
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    overall = summary["overall"]
    lines.extend(f"| {key} | {overall.get(key, 0.0):.4f} |" for key in metric_keys)
    denominators = overall.get("metric_denominators") or {}
    if denominators:
        lines.extend(["", "## Metric Denominators", "", "| Metric | Cases |", "| --- | ---: |"])
        lines.extend(f"| {key} | {denominators.get(key, 0)} |" for key in metric_keys)
    lines.extend(["", "## By Category", ""])
    lines.extend(_group_table(summary["by_category"], metric_keys))
    lines.extend(["", "## By Difficulty", ""])
    lines.extend(_group_table(summary["by_difficulty"], metric_keys))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_writable_index_dir(source_dir: Path, runtime_dir: Path) -> Path:
    source = Path(source_dir)
    dest = Path(runtime_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for filename in (
        "index.faiss",
        "payloads.jsonl",
        "id_map.json",
        "payload_offsets.pkl",
        "payloads_export.csv",
    ):
        src = source / filename
        if not src.exists():
            continue
        target = dest / filename
        if target.exists() or target.is_symlink():
            continue
        try:
            os.symlink(src, target)
        except OSError:
            shutil.copy2(src, target)

    src_cache = source / "payload_cache.sqlite"
    dest_cache = dest / "payload_cache.sqlite"
    payloads_path = dest / "payloads.jsonl"
    if src_cache.exists() and payloads_path.exists() and not dest_cache.exists():
        shutil.copy2(src_cache, dest_cache)
        stat = payloads_path.stat()
        conn = sqlite3.connect(str(dest_cache))
        try:
            conn.execute("UPDATE meta SET value=? WHERE key='payload_size'", (str(stat.st_size),))
            conn.execute("UPDATE meta SET value=? WHERE key='payload_mtime_ns'", (str(stat.st_mtime_ns),))
            conn.commit()
        finally:
            conn.close()
    return dest


def _group_table(groups: dict[str, Any], metric_keys: list[str]) -> list[str]:
    header = ["Group", "Count", *metric_keys]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---", "---:"] + ["---:"] * len(metric_keys)) + " |"]
    for group, values in groups.items():
        cells = [group, str(values.get("count", 0)), *[f"{values.get(key, 0.0):.4f}" for key in metric_keys]]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())

