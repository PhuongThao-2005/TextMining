# Phân công
## Nguyên tắc phân công

Ai phụ trách chính phần nào thì cũng là người chạy ablation cho phần đó.

Phân công chung:

* [Người 1 - Bình]: benchmark, data contract, config matrix, runbook, kiểm tra tính hợp lệ của toàn bộ run.
* [Người 2 - Thảo]: Dense retrieval, vector index, embedding ablation, chunk-size ablation.
* [Người 3 - Kiệt]: Sparse retrieval, Hybrid, RRF, Cross-Encoder reranker ablation.
* [Người 4 - Lý]: Graph RAG, Dense+Graph, Hybrid+Graph, graph-related ablation.
* [Người 5 - My]: E2E runner, LLM/agent ablation, UI demo, tổng hợp report cuối.

Mốc công việc:

* Giai đoạn 1: 3 ngày chuẩn bị pipeline, notebook, script, UI, smoke test.
* Giai đoạn 2: tuần sau treo máy chạy full ablation.
* Giai đoạn 3: tổng hợp, phân tích, viết report kết quả.

---

# [Người 1 - Bình] — Benchmark, config matrix, runbook, kiểm soát chất lượng run

## Vai trò

Người 1 chịu trách nhiệm đảm bảo tất cả ablation chạy trên cùng benchmark, cùng corpus snapshot, cùng format output. Người 1 không cần chạy một nhóm ablation model riêng, nhưng phải kiểm tra mọi run của các bạn khác có hợp lệ để so sánh hay không.

## Giai đoạn 1 — Chuẩn bị trong 3 ngày

### Công việc

* Chốt path QA benchmark chính thức.
* Ghi rõ benchmark version.
* Kiểm tra benchmark có đủ field:
  * `qa_id`
  * `question`
  * `reference_answer` hoặc `answer`
  * `answer_type`
  * `category`
  * `difficulty`
  * `ground_truth.chunk_ids`
  * `ground_truth.provision_ids` nếu có
  * `edges_used` nếu có graph/cross-document
* Chốt path data artifact:
  * `documents.jsonl`
  * `provisions.jsonl`
  * `chunks.jsonl`
  * `edges.jsonl`
  * `validity_timeline.jsonl`
  * `authority_index.jsonl`
* Tạo file config matrix:

```text
configs/ablation_configs.yaml
```

* Tạo manifest schema cho mọi run.
* Tạo runbook:

```text
docs/ablation_runbook.md
```

### Config cần khai báo trong matrix

* `Embed-ChunkOnly-Dense`
* `Embed-ChunkMeta-Dense`
* `Retrieval-DenseOnly`
* `Retrieval-Hybrid-SparseDense`
* `Retrieval-Dense-Graph`
* `Retrieval-Hybrid-SparseDense-Graph`
* `Rerank-None-Hybrid`
* `Rerank-RRF-Hybrid`
* `Rerank-CrossEncoder-Hybrid`
* `Rerank-RRFPlusCrossEncoder-Hybrid`
* `LLM-BaseReasoning`
* `LLM-CoTReasoning`
* `LLM-LargerModel`
* `LLM-LargerModel-CoTReasoning`
* `Agent-None-PlainRAG`
* `Agent-SimplePlanner`
* `Agent-MultiTool-Orchestrated`
* Chunk-size configs nếu kịp build index.

### Output format bắt buộc

Mỗi run phải ghi vào:

```text
evaluation_runs/
  ablation/
    <run_id>/
      manifest.json
      retrieval_cases.jsonl
      retrieval_metrics.json
      e2e_predictions.jsonl
      e2e_metrics.json
      latency.json
      report.md
```

`manifest.json` phải có:

* `run_id`
* `config_name`
* `benchmark_path`
* `benchmark_version`
* `corpus_version`
* `index_path` hoặc `collection`
* `graph_artifact_path`
* `retriever_config`
* `generator_config`
* `top_k`
* `filter_profile`
* `timestamp`
* `git_commit` nếu có

## Giai đoạn 2 — Khi tuần sau chạy full ablation

### Công việc

* Trước khi các bạn chạy full, kiểm tra:
  * benchmark path đúng
  * config name đúng
  * output dir chưa tồn tại hoặc không overwrite
  * manifest ghi đủ thông tin
* Sau mỗi run của Người 2/3/4/5, kiểm tra run có hợp lệ:
  * cùng benchmark
  * cùng corpus version
  * không thiếu metrics
  * không thiếu latency
  * số lượng QA evaluated hợp lý
  * số lượng skipped có lý do
* Lập bảng trạng thái:
  * ready
  * running
  * completed
  * failed
  * needs rerun
  * deferred

## Giai đoạn 3 — Sau khi chạy xong ablation

### Công việc

* Kiểm tra tất cả `manifest.json`.
* Loại khỏi bảng so sánh các run sai benchmark/corpus.
* Ghi chú run nào failed hoặc deferred.
* Hỗ trợ Người 5 viết phần "experiment setup" trong report.

## Deliverables

* Benchmark path chính thức.
* Data artifact path chính thức.
* `configs/ablation_configs.yaml`.
* `docs/ablation_runbook.md`.
* Manifest schema.
* Bảng trạng thái run.
* Danh sách run hợp lệ để đưa vào final report.

## Tiêu chí hoàn thành

* Mọi full run đều có manifest hợp lệ.
* Không có kết quả nào bị trộn sai benchmark/corpus.
* Người 5 có đủ metadata để tổng hợp report cuối.

---

# [Người 2 - Thảo] — Dense retrieval, embedding ablation, chunk-size ablation

## Vai trò

Người 2 chịu trách nhiệm build và chạy ablation cho Dense retrieval. Đây là baseline để so sánh với Hybrid, Graph và các biến thể khác.

## Giai đoạn 1 — Chuẩn bị trong 3 ngày

### Công việc

* Xác nhận Dense baseline chạy được bằng FAISS hoặc Qdrant.
* Nếu FAISS, xác nhận có:
  * `index.faiss`
  * `payloads.jsonl`
* Nếu Qdrant, xác nhận collection retrieval được.
* Chạy smoke retrieval trên QA benchmark.
* Chuẩn bị hai embedding config:
  * `Embed-ChunkOnly-Dense`
  * `Embed-ChunkMeta-Dense`
* Nếu chunk-only index chưa có, chuẩn bị script/notebook build và ghi thời gian build dự kiến.
* Log latency Dense retrieval:
  * total retrieval latency
  * embedding latency nếu đo được
  * vector search latency nếu đo được
  * top-k/top-n

### Notebook/script phụ trách

```text
notebooks/vector_retrieval_eval.ipynb
```

Nếu cần build lại index:

```text
scripts/build_vector_index.py
```

## Giai đoạn 2 — Chạy full ablation

Người 2 trực tiếp chạy các ablation:

| Config | Mục tiêu |
| --- | --- |
| `Retrieval-DenseOnly` | Dense baseline chính |
| `Embed-ChunkMeta-Dense` | Baseline embedding có metadata |
| `Embed-ChunkOnly-Dense` | So sánh tác động của metadata |
| Chunk-size ablation | Chạy nếu có thời gian build lại index |

### Lệnh chạy dự kiến

```bash
python scripts/run_ablation_config.py --config Retrieval-DenseOnly
python scripts/run_ablation_config.py --config Embed-ChunkMeta-Dense
python scripts/run_ablation_config.py --config Embed-ChunkOnly-Dense
```

Chunk-size chỉ chạy khi index đã sẵn sàng:

```bash
python scripts/run_ablation_config.py --config ChunkSize-<size>
```

### Trong lúc chạy cần theo dõi

* Index load được không.
* Retrieval latency có tăng bất thường không.
* Recall@k/MRR/nDCG có output không.
* Context recall trong E2E có hợp lý không.
* Chunk-only và chunk+metadata có dùng đúng index không.

## Giai đoạn 3 — Phân tích kết quả

Người 2 viết nhận xét cho phần Dense/Embedding:

* Dense baseline mạnh/yếu ở category nào.
* Metadata giúp hay làm giảm retrieval.
* Chunk-only có nhanh hơn không.
* Trade-off giữa quality và latency.
* Nếu chunk-size chạy được: chunk size nào tốt nhất.

## Deliverables

* Dense baseline smoke pass.
* Dense full run.
* Embedding ablation full run.
* Chunk-size run nếu kịp.
* `notebooks/vector_retrieval_eval.ipynb`.
* Output run trong `evaluation_runs/ablation/`.
* Nhận xét Dense/Embedding để đưa vào report.

## Tiêu chí hoàn thành

* Có kết quả `Retrieval-DenseOnly`.
* Có kết quả so sánh `Embed-ChunkOnly-Dense` vs `Embed-ChunkMeta-Dense`.
* Có latency Dense retrieval.
* Có kết luận config Dense nào làm baseline chính.

---

# [Người 3 - Kiệt] — Sparse retrieval, Hybrid, RRF, Cross-Encoder

## Vai trò

Người 3 chịu trách nhiệm build và chạy ablation cho Hybrid retrieval và reranker.

## Giai đoạn 1 — Chuẩn bị trong 3 ngày

### Công việc

* Kiểm tra đã có BM25/Sparse retriever chưa.
* Nếu chưa có, tạo sparse retriever tối thiểu trên `chunk_text`.
* Sparse retriever phải trả về:
  * `chunk_id`
  * `chunk_text`
  * score
  * rank
  * citation/payload nếu có
* Tạo sparse index có thể load lại.
* Implement Hybrid:
  * Dense search top-k.
  * Sparse search top-k.
  * RRF fusion.
  * Dedupe theo `chunk_id`.
  * Output cùng schema với Dense.
* Thêm Cross-Encoder reranker nếu kịp.
* Log latency:
  * dense latency
  * sparse latency
  * fusion latency
  * cross-encoder latency
  * total retrieval latency

### Notebook/script phụ trách

```text
notebooks/hybrid_retrieval_eval.ipynb
scripts/build_sparse_index.py
```

## Giai đoạn 2 — Chạy full ablation

Người 3 trực tiếp chạy các ablation:

| Config | Mục tiêu |
| --- | --- |
| `Retrieval-Hybrid-SparseDense` | So sánh Hybrid với Dense |
| `Rerank-None-Hybrid` | Hybrid không rerank |
| `Rerank-RRF-Hybrid` | Hybrid dùng RRF |
| `Rerank-CrossEncoder-Hybrid` | Cross-Encoder only |
| `Rerank-RRFPlusCrossEncoder-Hybrid` | RRF lấy candidates + CE rerank |

### Lệnh chạy dự kiến

```bash
python scripts/run_ablation_config.py --config Retrieval-Hybrid-SparseDense
python scripts/run_ablation_config.py --config Rerank-None-Hybrid
python scripts/run_ablation_config.py --config Rerank-RRF-Hybrid
python scripts/run_ablation_config.py --config Rerank-CrossEncoder-Hybrid
python scripts/run_ablation_config.py --config Rerank-RRFPlusCrossEncoder-Hybrid
```

Nếu Cross-Encoder quá chậm:

* Chạy subset trước.
* Ghi estimated full runtime.
* Nếu không đủ thời gian thì đánh dấu deferred.

### Trong lúc chạy cần theo dõi

* Sparse index load đúng không.
* Dense và Sparse có cùng corpus/index không.
* RRF có dedupe đúng không.
* Cross-Encoder có vượt thời gian/quota không.
* Latency của reranker có đáng đổi lấy quality không.

## Giai đoạn 3 — Phân tích kết quả

Người 3 viết nhận xét cho phần Hybrid/Reranker:

* Hybrid có cải thiện Recall@k so với Dense không.
* RRF có tốt hơn raw hybrid không.
* Cross-Encoder có cải thiện answer quality không.
* Cross-Encoder có quá chậm để dùng trong demo/UI không.
* Config reranker nào đáng chọn làm main pipeline.

## Deliverables

* Sparse/BM25 index hoặc retriever tối thiểu.
* `scripts/build_sparse_index.py`.
* `notebooks/hybrid_retrieval_eval.ipynb`.
* Full run cho Hybrid/RRF.
* Cross-Encoder full run hoặc defer note.
* Latency Dense/Sparse/Fusion/Rerank.
* Nhận xét Hybrid/Reranker để đưa vào report.

## Tiêu chí hoàn thành

* Có kết quả `Retrieval-Hybrid-SparseDense`.
* Có ít nhất một kết quả reranker.
* Có kết luận Hybrid/Reranker có đáng dùng hơn Dense hay không.

---

# [Người 4 - Lý] — Graph RAG integration và Graph ablation

## Vai trò

Người 4 chịu trách nhiệm tích hợp graph vào retrieval và chạy Graph RAG ablation.

## Giai đoạn 1 — Chuẩn bị trong 3 ngày

### Công việc

* Xác nhận graph build/load được từ data hiện có.
* Tạo hoặc chốt graph artifact/pickle.
* Test traversal modes:
  * `basis`
  * `guidance`
  * `validity`
  * `structure`
  * `neighbors`
* Tích hợp Graph retrieval:
  * Dense pre-pass lấy seed chunks.
  * Map seed chunks sang graph start IDs.
  * Traverse graph.
  * Lấy chunk liên quan từ store.
  * Fuse seed + graph expansion + traversal chunks.
  * Dedupe theo `chunk_id`.
* Đặt giới hạn graph:
  * max starts
  * max depth
  * max graph chunks
  * top-n context cuối cùng
* Log graph:
  * seed count
  * traversal start count
  * graph expansion count
  * traversal added chunks
  * graph latency
  * total retrieval latency

### Notebook/script phụ trách

```text
notebooks/graph_rag_eval.ipynb
```

## Giai đoạn 2 — Chạy full ablation

Người 4 trực tiếp chạy các ablation:

| Config | Mục tiêu |
| --- | --- |
| `Retrieval-Dense-Graph` | Đo tác động của Graph trên Dense |
| `Retrieval-Hybrid-SparseDense-Graph` | Đo full retrieval stack |

### Lệnh chạy dự kiến

```bash
python scripts/run_ablation_config.py --config Retrieval-Dense-Graph
python scripts/run_ablation_config.py --config Retrieval-Hybrid-SparseDense-Graph
```

Nếu Graph traversal chậm:

* Giảm max depth/max starts.
* Chạy subset theo category graph-heavy trước.
* Ghi estimated full runtime.

### Trong lúc chạy cần theo dõi

* Graph artifact load đúng không.
* Graph có trả về quá nhiều context không.
* Multi-hop/cross-document/legal-validity có cải thiện không.
* Latency Graph có quá cao không.
* Graph có làm giảm precision vì thêm context nhiễu không.

## Giai đoạn 3 — Phân tích kết quả

Người 4 viết nhận xét cho phần Graph:

* Graph cải thiện category nào.
* Graph làm giảm category nào.
* Graph tăng context recall hay chỉ tăng nhiễu.
* Latency Graph có chấp nhận được không.
* Nên chọn Dense+Graph hay Hybrid+Graph làm main pipeline.

## Deliverables

* Graph artifact/pickle path.
* `notebooks/graph_rag_eval.ipynb`.
* Full run `Retrieval-Dense-Graph`.
* Full run `Retrieval-Hybrid-SparseDense-Graph` nếu kịp.
* Graph latency.
* Case analysis graph improve/degrade.
* Nhận xét Graph để đưa vào report.

## Tiêu chí hoàn thành

* Graph được nối vào retrieval pipeline thật.
* Có kết quả ít nhất `Retrieval-Dense-Graph`.
* Có kết luận Graph có đáng thêm vào pipeline chính hay không.

---

# [Người 5 - My] — E2E runner, LLM/Agent ablation, UI, final report

## Vai trò

Người 5 chịu trách nhiệm chạy E2E, LLM/Agent ablation, UI demo và tổng hợp kết quả cuối.

Người 5 chạy LLM/Agent trên cùng official Dense+BM25+RRF+Cross-Encoder+Graph
stack đã bàn giao và được canonical full-stack adapter tích hợp. Mọi config phải
dùng cùng benchmark, corpus, FAISS, BM25, graph artifact và retrieval parameters.

## Giai đoạn 1 — Chuẩn bị trong 3 ngày

### Công việc

* Tạo hoặc mở rộng:

```text
scripts/run_ablation_config.py
scripts/run_ablation_batch.py
```

* Runner phải:
  * đọc `configs/ablation_configs.yaml`
  * load đúng retriever stack
  * chạy retrieval
  * chạy generator hoặc reference generator
  * tính metrics
  * ghi output vào `evaluation_runs/ablation/<run_id>/`
  * không crash toàn bộ run nếu một case lỗi
* Ghi E2E metrics:
  * Exact Match
  * Token F1
  * ROUGE-L
  * Unanswerable Accuracy
  * Context Recall@k
  * breakdown theo category
  * breakdown theo answer_type
  * breakdown theo difficulty
* Ghi latency:
  * total
  * dense retrieve
  * sparse retrieve
  * graph traversal
  * fusion
  * rerank
  * generation

### UI demo

Tạo UI:

```text
app.py
```

hoặc:

```text
ui/app.py
```

Khuyến nghị dùng Streamlit.

UI cần có:

* ô nhập câu hỏi
* dropdown chọn retrieval config
* top-k input
* filter profile
* toggle Graph
* toggle Reranker
* nút Ask
* answer area
* context table
* latency table
* error/warning area

Tạo hướng dẫn UI:

```text
docs/ui_demo.md
```

### Report aggregation

Tạo:

```text
scripts/aggregate_ablation_results.py
notebooks/ablation_report.ipynb
```

## Giai đoạn 2 — Chạy full ablation

Người 5 trực tiếp chạy các ablation:

| Config | Mục tiêu |
| --- | --- |
| `LLM-BaseReasoning` | Baseline LLM/prompt |
| `LLM-CoTReasoning` | Đo tác động reasoning prompt |
| `LLM-LargerModel` | Đo tác động model mạnh hơn |
| `LLM-LargerModel-CoTReasoning` | Đo tương tác giữa model mạnh hơn và reasoning prompt |
| `Agent-None-PlainRAG` | Plain RAG baseline |
| `Agent-SimplePlanner` | Agent planner đơn giản |
| `Agent-MultiTool-Orchestrated` | Agent nhiều tool nếu kịp |

### Lệnh chạy dự kiến

```bash
python scripts/run_ablation_config.py --config LLM-BaseReasoning
python scripts/run_ablation_config.py --config LLM-CoTReasoning
python scripts/run_ablation_config.py --config LLM-LargerModel
python scripts/run_ablation_config.py --config LLM-LargerModel-CoTReasoning
python scripts/run_ablation_config.py --config Agent-None-PlainRAG
python scripts/run_ablation_config.py --config Agent-SimplePlanner
python scripts/run_ablation_config.py --config Agent-MultiTool-Orchestrated
```

Batch full run:

```bash
python scripts/run_ablation_batch.py --configs Retrieval-DenseOnly Retrieval-Hybrid-SparseDense Retrieval-Dense-Graph Retrieval-Hybrid-SparseDense-Graph
```

### Trong lúc chạy cần theo dõi

* Generator API/quota/rate limit.
* Lỗi per-case.
* Output có đầy đủ metrics không.
* Latency generation có quá cao không.
* Agent có gọi retrieval đúng không.
* UI có dùng được config main pipeline không.
* Preflight phải xác nhận đủ FAISS, BM25 và graph artifacts trước khi gọi provider.
* Manifest phải xác nhận benchmark/corpus/index và retrieval stack đã freeze.

## Giai đoạn 3 — Tổng hợp và viết report cuối

Người 5 chịu trách nhiệm tổng hợp tất cả run:

```bash
python scripts/aggregate_ablation_results.py --runs-dir evaluation_runs/ablation
```

Output:

```text
evaluation_runs/ablation/ablation_summary.csv
evaluation_runs/ablation/ablation_report.md
```

Bảng tổng hợp cần có:

* config name
* EM
* Token F1
* ROUGE-L
* Unanswerable Accuracy
* Context Recall@k
* Recall@1/5/10 nếu có
* MRR
* nDCG
* Average Latency
* Median Latency
* Notes/Failure

Report cuối cần có:

* Retrieval ablation table.
* Embedding ablation table.
* Reranker ablation table.
* Graph ablation table.
* LLM ablation table.
* Agent ablation table nếu có.
* Latency-quality trade-off.
* Kết luận config tốt nhất.
* Các config deferred và lý do.

## Deliverables

* `scripts/run_ablation_config.py`.
* `scripts/run_ablation_batch.py`.
* `notebooks/e2e_rag_eval.ipynb`.
* `app.py` hoặc `ui/app.py`.
* `docs/ui_demo.md`.
* `scripts/aggregate_ablation_results.py`.
* `notebooks/ablation_report.ipynb`.
* Full run LLM/Agent nếu đủ quota.
* `ablation_summary.csv`.
* `ablation_report.md`.
* UI demo chạy local được.

## Tiêu chí hoàn thành

* Runner chạy được config theo tên.
* UI hỏi đáp được và hiển thị context/citation/latency.
* Có kết quả E2E cho baseline.
* Có final ablation summary.
* Có kết luận config nào nên dùng trong pipeline chính.

---

# Thứ tự chạy full ablation tuần sau

Ưu tiên chạy theo thứ tự sau:

1. Người 2 chạy Dense baseline và embedding ablation.
2. Người 3 chạy Hybrid/RRF/reranker ablation.
3. Người 4 chạy Graph ablation.
4. Người 5 chạy LLM ablation.
5. Người 5 chạy Agent ablation nếu pipeline ổn.
6. Người 2 chạy chunk-size ablation nếu có thời gian build index.
7. Người 5 tổng hợp toàn bộ report cuối.

---

# Deliverables cuối cùng khi xong ablation

| Deliverable | Phụ trách chính |
| --- | --- |
| Benchmark/config/run manifest hợp lệ | Người 1 |
| `Retrieval-DenseOnly` result | Người 2 |
| `Embed-ChunkOnly-Dense` result | Người 2 |
| `Embed-ChunkMeta-Dense` result | Người 2 |
| Chunk-size result nếu có | Người 2 |
| `Retrieval-Hybrid-SparseDense` result | Người 3 |
| `Rerank-None-Hybrid` result | Người 3 |
| `Rerank-RRF-Hybrid` result | Người 3 |
| `Rerank-CrossEncoder-Hybrid` result/defer note | Người 3 |
| `Rerank-RRFPlusCrossEncoder-Hybrid` result/defer note | Người 3 |
| `Retrieval-Dense-Graph` result | Người 4 |
| `Retrieval-Hybrid-SparseDense-Graph` result | Người 4 |
| Graph improve/degrade analysis | Người 4 |
| `LLM-BaseReasoning` result | Người 5 |
| `LLM-CoTReasoning` result | Người 5 |
| `LLM-LargerModel` result | Người 5 |
| `LLM-LargerModel-CoTReasoning` result | Người 5 |
| Agent results/defer note | Người 5 |
| UI demo | Người 5 |
| `ablation_summary.csv` | Người 5 |
| `ablation_report.md` | Người 5 |

---

# Definition of Done toàn bộ

Ablation được xem là hoàn thành khi:

* Mỗi config chạy xong đều có `manifest.json`.
* Mỗi config chạy xong đều có metrics và latency.
* Các run sai benchmark/corpus bị loại khỏi bảng so sánh.
* Có bảng so sánh chất lượng và latency.
* Có kết luận:
  * Dense vs Hybrid vs Graph stack nào tốt nhất.
  * Embed metadata có giúp không.
  * Reranker nào đáng dùng.
  * Graph có đáng thêm không.
  * LLM/Agent có cải thiện không.
* Có UI demo dùng được với config pipeline tốt nhất.
* Có `ablation_report.md` để đưa vào báo cáo/paper.
