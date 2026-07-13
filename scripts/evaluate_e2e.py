#!/usr/bin/env python3
"""Run end-to-end RAG evaluation on a frozen QA benchmark."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.io_utils import qa_id, read_jsonl, write_json, write_jsonl  # noqa: E402
from evaluation.metrics import aggregate, aggregate_by, exact_match, is_unanswerable_text, rouge_l, token_f1  # noqa: E402
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
    parser.add_argument("--collection", default="legal_chunks")
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--qdrant-api-key", default=None)
    parser.add_argument("--retrieval-model", default="intfloat/multilingual-e5-large")
    parser.add_argument("--score-threshold", type=float, default=0.3)
    parser.add_argument("--no-expand-units", action="store_true")
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
            qdrant_url=args.qdrant_url,
            qdrant_api_key=args.qdrant_api_key,
            collection_name=args.collection,
            model=args.retrieval_model,
            top_k=max(args.retrieval_top_k * 3, 30),
            top_n=args.retrieval_top_k,
            score_threshold=args.score_threshold,
            expand_units=not args.no_expand_units,
        )
    )

    gemini: GeminiClient | None = None
    if args.generator == "gemini" or args.judge == "gemini":
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var {args.api_key_env!r}.")
        gemini = GeminiClient(api_key=api_key, rpm=args.rpm)

    cases: list[dict[str, Any]] = []
    for index, qa in enumerate(read_jsonl(args.qa_path), start=1):
        if args.limit is not None and len(cases) >= args.limit:
            break
        result = retriever.retrieve(str(qa.get("question") or ""), filter_profile=args.filter_profile, top_n=args.retrieval_top_k)
        context = format_context(result.chunks)
        reference_answer = str(qa.get("reference_answer") or qa.get("answer") or "")
        if args.generator == "reference":
            predicted = reference_answer
        else:
            assert gemini is not None
            predicted = gemini.generate(
                model=args.generator_model,
                prompt=ANSWER_PROMPT.format(
                    question=qa.get("question") or "",
                    answer_type=qa.get("answer_type") or "",
                    context=context,
                ),
            )

        row = score_case(qa, index, predicted, reference_answer, result.chunks)
        row["retrieved_context"] = [
            {
                "rank": rank,
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.id_str,
                "provision_id": chunk.parent_unit_id,
                "text": chunk.chunk_text,
                "score": chunk.rerank_score,
                "citation": chunk.citation_anchor or chunk.citation_label,
            }
            for rank, chunk in enumerate(result.chunks, start=1)
        ]
        if args.judge == "gemini":
            assert gemini is not None
            row["llm_judge"] = judge_with_gemini(gemini, args.judge_model, qa, reference_answer, predicted, context)
            row["judge_correctness"] = row["llm_judge"]["correctness"]
            row["judge_faithfulness"] = row["llm_judge"]["faithfulness"]
            row["judge_answer_relevancy"] = row["llm_judge"]["answer_relevancy"]
        cases.append(row)
        if len(cases) % 10 == 0:
            print(f"Evaluated {len(cases)} end-to-end cases...")

    metric_keys = ["exact_match", "token_f1", "rouge_l", "unanswerable_accuracy", "context_recall@k"]
    if args.judge == "gemini":
        metric_keys.extend(["judge_correctness", "judge_faithfulness", "judge_answer_relevancy"])
    summary = {
        "qa_path": str(args.qa_path),
        "config": {
            "collection": args.collection,
            "qdrant_url": args.qdrant_url,
            "retrieval_model": args.retrieval_model,
            "retrieval_top_k": args.retrieval_top_k,
            "filter_profile": args.filter_profile,
            "generator": args.generator,
            "generator_model": args.generator_model,
            "judge": args.judge,
            "judge_model": args.judge_model if args.judge == "gemini" else None,
        },
        "overall": aggregate(cases, metric_keys),
        "by_category": aggregate_by(cases, "category", metric_keys),
        "by_answer_type": aggregate_by(cases, "answer_type", metric_keys),
        "by_difficulty": aggregate_by(cases, "difficulty", metric_keys),
    }
    write_jsonl(args.out_dir / "e2e_predictions.jsonl", cases)
    write_json(args.out_dir / "e2e_metrics.json", summary)
    write_report(args.out_dir / "e2e_report.md", summary, metric_keys)
    print(f"E2E predictions: {args.out_dir / 'e2e_predictions.jsonl'}")
    print(f"E2E metrics: {args.out_dir / 'e2e_metrics.json'}")
    return 0


def format_context(chunks: list[Any]) -> str:
    blocks = []
    for rank, chunk in enumerate(chunks, start=1):
        citation = chunk.citation_anchor or chunk.citation_label or chunk.parent_unit_id or chunk.chunk_id
        blocks.append(
            f"[{rank}] chunk_id={chunk.chunk_id}; provision_id={chunk.parent_unit_id}; document_id={chunk.id_str}; citation={citation}\n"
            f"{chunk.chunk_text}"
        )
    return "\n\n".join(blocks)


def score_case(
    qa: dict[str, Any],
    index: int,
    predicted: str,
    reference_answer: str,
    chunks: list[Any],
) -> dict[str, Any]:
    answer_type = str(qa.get("answer_type") or "").lower()
    category = str(qa.get("category") or "").lower()
    gt = qa.get("ground_truth") or {}
    gt_chunks = {str(value) for value in gt.get("chunk_ids") or [] if value}
    retrieved = {chunk.chunk_id for chunk in chunks}
    is_unanswerable = answer_type == "unanswerable" or category == "unanswerable"
    unanswerable_ok = is_unanswerable_text(predicted) if is_unanswerable else not is_unanswerable_text(predicted)
    context_recall = len(gt_chunks & retrieved) / len(gt_chunks) if gt_chunks else (1.0 if is_unanswerable else 0.0)
    row = {
        "qa_id": qa_id(qa, index),
        "question": qa.get("question"),
        "category": qa.get("category"),
        "difficulty": qa.get("difficulty"),
        "answer_type": qa.get("answer_type"),
        "reference_answer": reference_answer,
        "predicted_answer": predicted,
        "ground_truth": gt,
        "exact_match": exact_match(_answer_for_exact_match(predicted, answer_type), _answer_for_exact_match(reference_answer, answer_type)),
        "token_f1": token_f1(predicted, reference_answer),
        "rouge_l": rouge_l(predicted, reference_answer),
        "unanswerable_accuracy": 1.0 if unanswerable_ok else 0.0,
        "context_recall@k": context_recall,
    }
    return row


def _answer_for_exact_match(answer: str, answer_type: str) -> str:
    if answer_type == "boolean":
        for line in answer.splitlines():
            line = line.strip()
            if line:
                return line
    return answer


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


def write_report(path: Path, summary: dict[str, Any], metric_keys: list[str]) -> None:
    lines = [
        "# End-to-End RAG Evaluation Report",
        "",
        f"- QA path: `{summary['qa_path']}`",
        f"- Evaluated QA: {summary['overall']['count']}",
        f"- Generator: `{summary['config']['generator_model']}`",
        f"- Retrieval top-k: {summary['config']['retrieval_top_k']}",
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
    lines.extend(["", "## By Answer Type", ""])
    lines.extend(_group_table(summary["by_answer_type"], metric_keys))
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
