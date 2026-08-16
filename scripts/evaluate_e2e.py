#!/usr/bin/env python3
"""Run end-to-end RAG evaluation on a frozen QA benchmark."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.e2e_runner import (  # noqa: E402
    METRIC_KEYS,
    format_context,
    read_benchmark_records,
    run_e2e_evaluation,
    score_case,
    write_e2e_artifacts,
    write_report,
)
from evaluation.retriever_factory import RetrieverRuntimeConfig, build_vector_retriever  # noqa: E402


ANSWER_PROMPT = """Bạn là hệ thống RAG pháp lý Việt Nam.
Chỉ trả lời dựa trên CONTEXT được cung cấp. Không suy diễn, không bịa thêm ngoài CONTEXT.
Nếu CONTEXT không đủ thông tin để trả lời, hãy trả lời: "Không có đủ thông tin trong ngữ cảnh được cung cấp."

Yêu cầu định dạng:
- Nếu answer_type là boolean: dòng đầu tiên chỉ được là "Có" hoặc "Không"; phần giải thích đặt sau dòng "Giải thích:".
- Nếu answer_type là unanswerable: chỉ nêu rằng không có đủ thông tin trong ngữ cảnh được cung cấp.
- Với các loại khác: trả lời ngắn gọn bằng tiếng Việt có dấu, có thể nêu căn cứ pháp lý nếu context có.

QUESTION:
{question}

ANSWER_TYPE:
{answer_type}

CONTEXT:
{context}

Trả lời bằng tiếng Việt có dấu:"""


JUDGE_PROMPT = """Bạn là giám khảo benchmark RAG pháp lý Việt Nam.
Chấm câu trả lời dự đoán dựa trên câu hỏi, đáp án tham chiếu và context đã retrieve.
Trả về JSON hợp lệ với các khóa:
- correctness: số từ 0 đến 1
- faithfulness: số từ 0 đến 1, fail mạnh nếu có hallucination ngoài context
- answer_relevancy: số từ 0 đến 1
- notes: nhận xét ngắn bằng tiếng Việt

QUESTION:
{question}

REFERENCE_ANSWER:
{reference_answer}

PREDICTED_ANSWER:
{predicted_answer}

RETRIEVED_CONTEXT:
{context}

JSON:"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate end-to-end RAG answers over a QA benchmark.")
    parser.add_argument("--qa-path", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("evaluation_runs/e2e"))
    parser.add_argument("--retrieval-top-k", type=int, default=10)
    parser.add_argument("--filter-profile", default="broad", choices=["current_law", "broad", "historical"])
    parser.add_argument("--retriever-backend", choices=["vector", "bm25"], default="vector")
    parser.add_argument("--store", choices=["faiss", "qdrant"], default="faiss")
    parser.add_argument("--index-dir", type=Path, default=Path("data/faiss_index"))
    parser.add_argument("--collection", default="legal_chunks")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--qdrant-api-key", default=None)
    parser.add_argument("--retrieval-model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--score-threshold", type=float, default=0.3)
    parser.add_argument("--no-expand-units", action="store_true")
    parser.add_argument("--bm25-service-url", default=None, help="Remote BM25 URL; defaults to BM25_SERVICE_URL.")
    parser.add_argument("--bm25-api-key", default=None, help="Remote BM25 API key; defaults to BM25_API_KEY.")
    parser.add_argument("--bm25-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--generator", choices=["gemini", "reference"], default="gemini")
    parser.add_argument("--generator-model", default="gemini-3.1-flash-lite")
    parser.add_argument("--judge", choices=["none", "gemini"], default="none")
    parser.add_argument("--judge-model", default="gemini-3.1-flash-lite")
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--rpm", type=int, default=15)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


class GeminiClient:
    def __init__(self, *, api_key: str, rpm: int) -> None:
        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("Install google-genai to use --generator gemini or --judge gemini.") from exc
        self.client = genai.Client(api_key=api_key)
        self.min_interval = 60.0 / max(1, rpm)
        self.last_call = 0.0

    def generate(self, *, model: str, prompt: str) -> str:
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        response = self.client.models.generate_content(model=model, contents=prompt)
        self.last_call = time.time()
        return str(getattr(response, "text", "") or "").strip()


def main() -> int:
    args = parse_args()
    retriever = build_vector_retriever(
        RetrieverRuntimeConfig(
            backend=args.retriever_backend,
            store=args.store,
            index_dir=args.index_dir,
            qdrant_url=args.qdrant_url,
            qdrant_api_key=args.qdrant_api_key,
            collection_name=args.collection,
            model=args.retrieval_model,
            top_k=max(args.retrieval_top_k * 3, 30),
            top_n=args.retrieval_top_k,
            score_threshold=args.score_threshold,
            expand_units=not args.no_expand_units,
            bm25_service_url=args.bm25_service_url,
            bm25_api_key=args.bm25_api_key,
            bm25_timeout_seconds=args.bm25_timeout_seconds,
        )
    )

    gemini: GeminiClient | None = None
    api_key = ""
    if args.generator == "gemini" or args.judge == "gemini":
        api_key = os.environ.get(args.api_key_env, "")
        if not api_key:
            raise RuntimeError(f"Missing API key env var {args.api_key_env!r}.")
        gemini = GeminiClient(api_key=api_key, rpm=args.rpm)

    def generate(qa: dict[str, Any], context: str, chunks: Sequence[Any]) -> str:
        del chunks
        reference_answer = str(qa.get("reference_answer") or qa.get("answer") or "")
        if args.generator == "reference":
            return reference_answer
        assert gemini is not None
        return gemini.generate(
            model=args.generator_model,
            prompt=ANSWER_PROMPT.format(
                question=qa.get("question") or "",
                answer_type=qa.get("answer_type") or "",
                context=context,
            ),
        )

    def judge(
        qa: dict[str, Any],
        reference_answer: str,
        predicted: str,
        context: str,
    ) -> dict[str, Any]:
        assert gemini is not None
        return judge_with_gemini(gemini, args.judge_model, qa, reference_answer, predicted, context)

    config = {
        "collection": args.collection,
        "backend": args.retriever_backend,
        "store": args.store,
        "bm25_service_url": args.bm25_service_url,
        "index_dir": str(args.index_dir),
        "qdrant_url": args.qdrant_url,
        "retrieval_model": args.retrieval_model,
        "retrieval_top_k": args.retrieval_top_k,
        "filter_profile": args.filter_profile,
        "generator": args.generator,
        "generator_model": args.generator_model,
        "judge": args.judge,
        "judge_model": args.judge_model if args.judge == "gemini" else None,
    }
    result = run_e2e_evaluation(
        read_benchmark_records(args.qa_path, limit=args.limit),
        retriever=retriever,
        generator=generate,
        retrieval_top_k=args.retrieval_top_k,
        filter_profile=args.filter_profile,
        judge=judge if args.judge == "gemini" else None,
        config=config,
        qa_path=str(args.qa_path),
        sensitive_values=[api_key, args.qdrant_api_key or ""],
    )
    artifacts = write_e2e_artifacts(args.out_dir, result, report_name="e2e_report.md")
    print(f"E2E predictions: {artifacts['predictions']}")
    print(f"E2E metrics: {artifacts['metrics']}")
    print(f"Latency: {artifacts['latency']}")
    print(f"Errors: {artifacts['errors']}")
    return 1 if result.counts["total_input"] and result.counts["successful"] == 0 else 0


def judge_with_gemini(
    gemini: GeminiClient,
    model: str,
    qa: dict[str, Any],
    reference_answer: str,
    predicted: str,
    context: str,
) -> dict[str, Any]:
    raw = gemini.generate(
        model=model,
        prompt=JUDGE_PROMPT.format(
            question=qa.get("question") or "",
            reference_answer=reference_answer,
            predicted_answer=predicted,
            context=context,
        ),
    )
    parsed = parse_jsonish(raw)
    return {
        "raw": raw,
        "correctness": float(parsed.get("correctness") or 0.0),
        "faithfulness": float(parsed.get("faithfulness") or 0.0),
        "answer_relevancy": float(parsed.get("answer_relevancy") or 0.0),
        "notes": str(parsed.get("notes") or ""),
    }


def parse_jsonish(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start : end + 1])
    return {}


__all__ = [
    "ANSWER_PROMPT",
    "JUDGE_PROMPT",
    "GeminiClient",
    "METRIC_KEYS",
    "format_context",
    "judge_with_gemini",
    "main",
    "parse_jsonish",
    "score_case",
    "write_report",
]


if __name__ == "__main__":
    raise SystemExit(main())

