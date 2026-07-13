# Evaluation Pipeline

Tài liệu này tóm tắt cách chạy benchmark đánh giá hệ retrieval và end-to-end RAG trên bộ QA đã frozen.
Nội dung ở đây đồng nhất với `docs/spec/SPEC_Benchmark.md`, trong đó phần benchmark construction và dataset schema có đầy đủ chi tiết.

## 1. Tổng quan

- Benchmark QA phải là file frozen, ví dụ `benchmark_v2.0.jsonl` hoặc file QA xuất ra như `qa_final.jsonl`.
- Evaluation gồm hai tầng:
  - Retrieval evaluation: đánh giá khả năng tìm evidence đúng bằng `ground_truth.chunk_ids`.
  - End-to-end evaluation: retriever + generator chạy thực tế, sau đó tính metric answer correctness và faithfulness.
- Mọi lần chạy phải ghi lại `corpus_version`, `benchmark_version`, `retriever_config`, `top_k`, `generator_model`, `timestamp`.

## 2. Điều kiện trước khi chạy

1. Đã build vector index bằng `scripts/build_vector_index.py`.
2. Qdrant đang chạy và chứa collection `legal_chunks` hoặc collection bạn chỉ định bằng `--collection`.
3. Có benchmark QA frozen, ví dụ `benchmark_v2.0.jsonl` hoặc `qa_final.jsonl`.
4. `docs/spec/SPEC_Benchmark.md` chứa chi tiết chuẩn về benchmark schema, categories, difficulty, và governance.

## 3. Retrieval benchmark

Retrieval benchmark đánh giá chất lượng retriever độc lập với generator.

```bash
python scripts/evaluate_retrieval.py \
  --qa-path /kaggle/working/qa_output/qa_final.jsonl \
  --out-dir /kaggle/working/eval_retrieval \
  --qdrant-url http://localhost:6333 \
  --collection legal_chunks \
  --top-k 1 5 10 \
  --filter-profile broad
```

Output:

- `retrieval_cases.jsonl`: mỗi QA kèm danh sách chunk retrieved và metric per-case.
- `retrieval_metrics.json`: summary tổng thể và breakdown theo `category`, `difficulty`, `answer_type`.
- `retrieval_report.md`: báo cáo đọc nhanh.

Metrics chính:

- `Recall@k` trên `ground_truth.chunk_ids`
- `Hit@k`
- `MRR@k`
- `nDCG@k`
- `Jaccard@k` (chunk-level)

## 4. End-to-end benchmark

End-to-end benchmark đánh giá cả retriever và generator trên cùng bộ QA.

### 4.1 Smoke test bằng reference generator

```bash
python scripts/evaluate_e2e.py \
  --qa-path /kaggle/working/qa_output/qa_final.jsonl \
  --out-dir /kaggle/working/eval_e2e_smoke \
  --qdrant-url http://localhost:6333 \
  --collection legal_chunks \
  --generator reference \
  --retrieval-top-k 10
```

### 4.2 Chạy RAG thực tế

```bash
set GEMINI_API_KEY=...
python scripts/evaluate_e2e.py \
  --qa-path /kaggle/working/qa_output/qa_final.jsonl \
  --out-dir /kaggle/working/eval_e2e \
  --qdrant-url http://localhost:6333 \
  --collection legal_chunks \
  --generator gemini \
  --generator-model gemini-3.1-flash-lite \
  --rpm 15 \
  --retrieval-top-k 10 \
  --filter-profile broad
```

### 4.3 Bật judge LLM

```bash
python scripts/evaluate_e2e.py \
  --qa-path /kaggle/working/qa_output/qa_final.jsonl \
  --out-dir /kaggle/working/eval_e2e_judged \
  --qdrant-url http://localhost:6333 \
  --collection legal_chunks \
  --generator gemini \
  --generator-model gemini-3.1-flash-lite \
  --judge gemini \
  --judge-model gemini-3.1-flash-lite \
  --rpm 15 \
  --retrieval-top-k 10
```

Output:

- `e2e_predictions.jsonl`: context retrieved, predicted answer, reference answer, metric per-case.
- `e2e_metrics.json`: summary tổng thể và breakdown.
- `e2e_report.md`: báo cáo đọc nhanh.

Metrics chính:

- `Exact Match`
- `Token F1`
- `ROUGE-L`
- `Unanswerable Accuracy`
- `Context Recall@k`
- `RAGAS Faithfulness` / `Context Precision` / `Answer Relevancy` nếu được hỗ trợ

## 5. Hướng dẫn đọc kết quả

- Nếu `Recall@10` thấp: lỗi chính nằm ở retriever/index/filter.
- Nếu `Context Recall@k` cao nhưng `Token F1`/`ROUGE-L` thấp: lỗi chính ở generator/prompt.
- Nếu `Unanswerable Accuracy` thấp: hệ thống đang trả lời quá tự tin khi context không đủ.
- Với QA `boolean`, `Exact Match` là metric chính vì câu trả lời chỉ nên là `Có` / `Không`.

## 6. Tham chiếu

- Xem thêm chi tiết benchmark construction, schema, category và governance tại `docs/spec/SPEC_Benchmark.md`.

