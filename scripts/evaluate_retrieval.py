#!/usr/bin/env python3
"""Run retrieval-only evaluation on a frozen QA benchmark."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.io_utils import qa_id, read_jsonl, write_json, write_jsonl  # noqa: E402
from evaluation.metrics import aggregate, aggregate_by, hit_at_k, jaccard_at_k, mrr_at_k, ndcg_at_k, recall_at_k  # noqa: E402
from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate chunk retrieval with Recall@k, MRR, nDCG, and Jaccard.")
    parser.add_argument("--qa-path", type=Path, required=True, help="Frozen QA JSONL, e.g. qa_final.jsonl.")
    parser.add_argument("--out-dir", type=Path, default=Path("evaluation_runs/retrieval"))
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 5, 10])
    parser.add_argument("--filter-profile", default="broad", choices=["current_law", "broad", "historical"])
    parser.add_argument("--collection", default="legal_chunks")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--qdrant-api-key", default=None)
    parser.add_argument("--model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--score-threshold", type=float, default=0.3)
    parser.add_argument("--no-expand-units", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Smoke-test on first N answerable QA.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_k = max(args.top_k)
    retriever = build_vector_retriever(
        RetrieverRuntimeConfig(
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
    for index, qa in enumerate(read_jsonl(args.qa_path), start=1):
        if str(qa.get("answer_type") or "").lower() == "unanswerable" or str(qa.get("category") or "").lower() == "unanswerable":
            skipped_unanswerable += 1
            continue
        gt = qa.get("ground_truth") or {}
        relevant = {str(chunk_id) for chunk_id in gt.get("chunk_ids") or [] if chunk_id}
        if not relevant:
            skipped_missing_gt += 1
            continue
        if args.limit is not None and len(cases) >= args.limit:
            break

        result = retriever.retrieve(str(qa.get("question") or ""), filter_profile=args.filter_profile, top_n=max_k)
        retrieved_ids = [chunk.chunk_id for chunk in result.chunks]
        row: dict[str, Any] = {
            "qa_id": qa_id(qa, index),
            "question": qa.get("question"),
            "category": qa.get("category"),
            "difficulty": qa.get("difficulty"),
            "answer_type": qa.get("answer_type"),
            "ground_truth_chunk_ids": sorted(relevant),
            "retrieved_chunk_ids": retrieved_ids,
            "retrieved": [
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
            ],
        }
        for k in args.top_k:
            row[f"recall@{k}"] = recall_at_k(retrieved_ids, relevant, k)
            row[f"hit@{k}"] = hit_at_k(retrieved_ids, relevant, k)
            row[f"mrr@{k}"] = mrr_at_k(retrieved_ids, relevant, k)
            row[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, relevant, k)
            row[f"jaccard@{k}"] = jaccard_at_k(retrieved_ids, relevant, k)
        cases.append(row)
        if len(cases) % 25 == 0:
            print(f"Evaluated {len(cases)} retrieval cases...")

    metric_keys = [f"{name}@{k}" for k in args.top_k for name in ("recall", "hit", "mrr", "ndcg", "jaccard")]
    summary = {
        "qa_path": str(args.qa_path),
        "retriever": {
            "collection": args.collection,
            "qdrant_url": args.qdrant_url,
            "model": args.model,
            "filter_profile": args.filter_profile,
            "score_threshold": args.score_threshold,
            "expand_units": not args.no_expand_units,
            "top_k": args.top_k,
        },
        "counts": {
            "evaluated_answerable": len(cases),
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
        f"- Evaluated answerable QA: {summary['counts']['evaluated_answerable']}",
        f"- Skipped unanswerable QA: {summary['counts']['skipped_unanswerable']}",
        f"- Skipped missing GT chunks: {summary['counts']['skipped_missing_ground_truth_chunks']}",
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    overall = summary["overall"]
    lines.extend(f"| {key} | {overall.get(key, 0.0):.4f} |" for key in metric_keys)
    lines.extend(["", "## By Category", ""])
    lines.extend(_group_table(summary["by_category"], metric_keys))
    lines.extend(["", "## By Difficulty", ""])
    lines.extend(_group_table(summary["by_difficulty"], metric_keys))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _group_table(groups: dict[str, Any], metric_keys: list[str]) -> list[str]:
    header = ["Group", "Count", *metric_keys]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---", "---:"] + ["---:"] * len(metric_keys)) + " |"]
    for group, values in groups.items():
        cells = [group, str(values.get("count", 0)), *[f"{values.get(key, 0.0):.4f}" for key in metric_keys]]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())

