#!/usr/bin/env python3
"""Compare local FAISS Dense retrieval with the remote Dense service."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever  # noqa: E402


DEFAULT_QUERIES = (
    "Người lao động được nghỉ hằng năm bao nhiêu ngày?",
    "Điều kiện hưởng trợ cấp thất nghiệp là gì?",
    "Người sử dụng lao động có được đơn phương chấm dứt hợp đồng lao động không?",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", default="data/chunk metadata")
    parser.add_argument("--dense-service-url", default=None)
    parser.add_argument("--dense-api-key", default=None)
    parser.add_argument("--model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--expected-index-version", default="chunk-metadata-faiss-v1")
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--filter-profile", default="broad")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--queries-path", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queries = _load_queries(args)
    local = build_vector_retriever(
        RetrieverRuntimeConfig(
            backend="vector",
            store="faiss",
            index_dir=_resolve_path(args.index_dir),
            model=args.model,
            top_k=args.top_k,
            top_n=args.top_n,
            score_threshold=0.3,
            expand_units=False,
        )
    )
    remote = build_vector_retriever(
        RetrieverRuntimeConfig(
            backend="dense_remote",
            model=args.model,
            top_k=args.top_k,
            top_n=args.top_n,
            score_threshold=0.3,
            expand_units=False,
            dense_service_url=args.dense_service_url,
            dense_api_key=args.dense_api_key,
            dense_expected_model=args.model,
            dense_expected_index_version=args.expected_index_version,
        )
    )

    rows: list[dict[str, Any]] = []
    for query in queries:
        local_result = local.retrieve(
            query,
            filter_profile=args.filter_profile,
            top_k=args.top_k,
            top_n=args.top_n,
            expand_units=False,
        )
        remote_result = remote.retrieve(
            query,
            filter_profile=args.filter_profile,
            top_k=args.top_k,
            top_n=args.top_n,
            expand_units=False,
        )
        local_chunks = list(local_result.chunks)
        remote_chunks = list(remote_result.chunks)
        row = {
            "query": query,
            "top1_match": _ids(local_chunks, 1) == _ids(remote_chunks, 1),
            "top5_match": _ids(local_chunks, 5) == _ids(remote_chunks, 5),
            "top10_match": _ids(local_chunks, 10) == _ids(remote_chunks, 10),
            "local_top10": _ids(local_chunks, 10),
            "remote_top10": _ids(remote_chunks, 10),
            "citation_anchor_match": _fields(local_chunks, "citation_anchor", 10) == _fields(remote_chunks, "citation_anchor", 10),
            "article_number_match": _fields(local_chunks, "article_number", 10) == _fields(remote_chunks, "article_number", 10),
            "score_order_match": _ids(sorted(local_chunks, key=lambda c: -c.vector_score), 10)
            == _ids(sorted(remote_chunks, key=lambda c: -c.vector_score), 10),
        }
        rows.append(row)

    ok = all(row["top1_match"] and row["top5_match"] and row["top10_match"] for row in rows)
    output = {"status": "pass" if ok else "fail", "cases": rows}
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"Dense parity: {output['status']}")
        for row in rows:
            print(f"- {row['query']}")
            print(f"  top1={row['top1_match']} top5={row['top5_match']} top10={row['top10_match']}")
            if not row["top10_match"]:
                print(f"  local:  {row['local_top10']}")
                print(f"  remote: {row['remote_top10']}")
    return 0 if ok else 1


def _load_queries(args: argparse.Namespace) -> list[str]:
    values = list(args.query)
    if args.queries_path is not None:
        text = args.queries_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                payload = json.loads(line)
                values.append(str(payload.get("question") or payload.get("query") or ""))
            else:
                values.append(line)
    return [value for value in values if value.strip()] or list(DEFAULT_QUERIES)


def _ids(chunks: list[Any], limit: int) -> list[str]:
    return [str(getattr(chunk, "chunk_id", "")) for chunk in chunks[:limit]]


def _fields(chunks: list[Any], field: str, limit: int) -> list[str]:
    return [str(getattr(chunk, field, "") or "") for chunk in chunks[:limit]]


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
