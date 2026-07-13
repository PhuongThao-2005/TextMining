# Evaluation Framework — Vietnamese Legal RAG System (FINAL)

**Corpus:** snapshot dataset v2 gồm các artifact chuẩn `documents.jsonl`, `provisions.jsonl`, `chunks.jsonl`, `edges.jsonl`, `text_provenance.jsonl`, `validity_timeline.jsonl`, `authority_index.jsonl` (G-LRAG v2) — với `id_str`, `unit_id`, `chunk_id` dùng chung một identity space.
**Cấu trúc dữ liệu:** Document (`id_str`) → Provision (`unit_id`, đơn vị trích dẫn) → Chunk (`chunk_id`, đơn vị embedding/retrieval); `provisions.jsonl` là unit citation, `chunks.jsonl` là unit embedding.
**Nguồn QA:** 100% grounded-generate từ corpus (`generated` + `manual`). ALQAC/vn-legal-instruct chỉ dùng làm tài liệu tham khảo văn phong, **không** đưa vào benchmark.

---

# 1. EVALUATION DATASET

## 1.1 Nguyên tắc bất biến

1. Corpus snapshot của các artifact v2 phải được freeze trước khi build QA — ghi hash + ngày trong `corpus_manifest.json`.
2. Ground truth neo vào `unit_id` (provision) là chính; `chunk_id` là **minimal supporting evidence** (chỉ những chunk thực sự cần để trả lời, không phải toàn bộ chunk của provision).
3. Ground truth được tạo **ngay lúc generate QA** (tự inherit từ provision nguồn và evidence đã được chọn) — **không** dùng retrieval để xác lập ground truth.
4. Retrieval chỉ xuất hiện ở 2 chỗ: (a) đánh giá hệ thống thật ở giai đoạn evaluation, (b) sanity-check chất lượng câu hỏi trên mẫu nhỏ lúc build — không bao giờ dùng để quyết định ground truth.
5. Benchmark **frozen** sau khi release — dùng chung cho mọi hệ retrieval (Dense/Hybrid/GraphRAG...) để đảm bảo so sánh công bằng.
6. Validity/authority phải được suy ra từ `validity_timeline.jsonl` và `authority_index.jsonl` theo `as_of_date`; `currency_status`/`legal_authority_rank` trong benchmark là thuộc tính được tính từ dataset, không phải nhãn cố định cũ.
7. Mọi QA multi-hop/cross-document/legal-validity phải ghi rõ `edges_used` với `rel_type` cụ thể, `direction_verified=true` và provenance tương ứng (không ghi chung chung "liên quan").
8. Batch generation là chi tiết triển khai, không làm giảm chất lượng benchmark: mỗi QA sinh ra trong batch phải độc lập, vẫn tuân diversity control và schema chuẩn.

## 1.2 Benchmark Construction Pipeline

```
Corpus (v2, frozen)
    │
    ▼
Representative Sampling
   (stratified theo document_type, legal_field_code, sector_code, legal_authority_rank, currency_status, độ dài văn bản)
    │
    ▼
Provision Role Classification
   (tra thẳng edges.jsonl / validity_timeline.jsonl / text_provenance.jsonl / authority_index.jsonl để xác định
    category được phép sinh — không đoán, không generate tự do)
    │
    ▼
Grounded Synthetic QA Generation
   (generate theo đúng category cho phép; mỗi call có thể sinh 1 batch QA độc lập
    cho cùng 1 provision, mặc định batch_size=4; multi-hop/cross-document dùng thêm provision
    liên quan qua edges; ground truth tự inherit từ nguồn đã dùng)
    │
    ▼
Minimal Evidence Tagging
   (xác định chunk_id tối thiểu thực sự chứa phần trả lời, không phải cả provision)
    │
    ▼
LLM Verification (1 lớp, checklist gộp 5 tiêu chí; verifier chạy theo batch, tối đa 5 RPM, retry cho 429, max_workers=1 cho Gemini Free)
    │
    ▼
Retrieval Sanity Check (nhẹ, chỉ chạy trên mẫu 10–15%, KHÔNG dùng để tạo ground truth)
    │
    ▼
Human Spot Check
    │
    ▼
Golden Benchmark (Frozen) — benchmark_v2.0.jsonl
```

### Diễn giải từng bước

**Representative Sampling** — Lấy mẫu provision theo tỷ lệ có kiểm soát (đặt trần trên theo `legal_field_code`) để tránh benchmark bị lệch về các lĩnh vực chiếm tỷ trọng lớn trong corpus (ví dụ dân sự), đảm bảo các lĩnh vực nhỏ hơn vẫn có đại diện tối thiểu.

**Provision Role Classification** — Trước khi generate, mỗi provision được phân loại category được phép sinh dựa trên dữ liệu có sẵn:

| Điều kiện dữ liệu | Category được phép |
|---|---|
| Không có edge liên kết và `currency_status(as_of_date)=in_force` | Single-hop |
| Có trace trong `text_provenance.jsonl` | Citation |
| Có edge `PROVISION_NEXT` nối các provision cùng document, nội dung phụ thuộc lẫn nhau | Multi-hop |
| Có edge `rel_*` với `direction_verified=true` và trỏ sang document khác | Cross-document |
| Có edge `rel_amends` / `rel_replaces` / `rel_refers_to` với `direction_verified=true` | Gắn thêm tag Graph Reasoning (xem 1.4) |
| Xuất hiện trong `validity_timeline.jsonl` | Legal Validity |
| Provision liền kề 1 chủ đề gần giống nhưng không quy định | Unanswerable |

**Grounded Synthetic QA Generation** — Sinh QA theo template xoay vòng (≥5 biến thể/category); mỗi LLM call có thể tạo một batch 3–5 QA độc lập cho cùng 1 provision, nhưng mỗi QA vẫn phải tuân diversity control: tối đa 2 QA/provision, tối đa ~3% tổng benchmark/document.

**Minimal Evidence Tagging** — Vì 1 provision có thể có nhiều chunk, chỉ gán chunk nào thực sự overlap với phần trả lời (theo tinh thần "minimal supporting evidence" của LegalBench-RAG), tránh việc Recall@K bị "ăn gian" khi hệ thống trả về nguyên provision dài.

**LLM Verification** — verifier có thể đánh giá đồng thời một batch QA (mặc định batch_size≈4) thay vì gọi riêng từng item, kiểm tra gộp: answer correctness, evidence sufficiency, no hallucination, category correctness, difficulty correctness. Fail bất kỳ tiêu chí nào → discard, không tự sửa.

**Retrieval Sanity Check** — Chạy Hybrid retriever Top-30 trên **mẫu 10-15%** QA đã pass verification, chỉ để phát hiện câu hỏi bị paraphrase trôi quá xa provision gốc (gắn cờ `low_lexical_alignment`), không dùng để tạo hay sửa ground truth.

**Human Spot Check** — ~15% tổng benchmark, phân bổ theo rủi ro (xem 1.6); 100% QA bị gắn cờ từ bước sanity check bắt buộc qua tay người.

## 1.3 Dataset Schema

```json
{
  "qa_id": "vlrag-000123",
  "question": "...",
  "reference_answer": "...",
  "answer_type": "extractive | abstractive | boolean | unanswerable",

  "ground_truth": {
    "document_ids": ["..."],
    "provision_ids": ["..."],
    "chunk_ids": ["..."]
  },

  "edges_used": [
    {"src_id": "...", "dst_id": "...", "rel_type": "...", "direction_verified": true}
  ],

  "category": "single_hop | citation | multi_hop | cross_document | legal_validity | unanswerable",
  "difficulty": "easy | medium | hard",

  "metadata": {
    "document_type": "...",
    "legal_field_code": "...",
    "sector_code": "...",
    "legal_authority_rank": 5,
    "currency_status": "in_force",
    "as_of_date": "2026-07-01",
    "corpus_version": "glrag-v2-2026-07-snapshot"
  },

  "source_type": "generated | manual",
  "generation_context": {
    "source_provision_ids": ["..."],
    "source_chunk_ids": ["..."],
    "evidence_provenance": "provisions.jsonl + chunks.jsonl",
    "batch_size": 4,
    "rate_limit_rpm": 5
  },
  "low_lexical_alignment": false,
  "human_reviewed": true,
  "human_reviewer_note": "",
  "status": "active"
}
```

## 1.4 Categories (đo theo năng lực RAG, không theo chủ đề luật)

| Category | Đo năng lực gì |
|---|---|
| **Single-hop Retrieval** | Tìm & trả lời đúng từ 1 provision đơn lẻ |
| **Citation** | Trích dẫn chính xác số điều/văn bản |
| **Multi-hop** | Kết hợp thông tin từ ≥2 provision cùng document |
| **Cross-document** | Đối chiếu/kết hợp thông tin từ ≥2 document khác nhau |
| **Legal Validity** | Xác định hiệu lực, văn bản thay thế, còn/hết hiệu lực theo thời gian |
| **Unanswerable** | Từ chối trả lời đúng khi corpus không có thông tin |

**Graph Reasoning** không tách thành category riêng — được đo **xuyên category** thông qua field `edges_used`: nếu quan hệ dùng để nối provision là quan hệ ngữ nghĩa có kiểu (`rel_amends`, `rel_replaces`, `rel_refers_to`...) thay vì chỉ quan hệ đọc liền mạch (`PROVISION_NEXT`), QA đó được tính vào subset "Graph Reasoning" khi báo cáo (xem mục 4).

## 1.5 Difficulty

- **Easy** — trả lời trọn trong 1 `unit_id`, extractive trực tiếp.
- **Medium** — cần tổng hợp ≥2 `unit_id` trong cùng 1 document, hoặc diễn giải/1 bước suy luận.
- **Hard** — cần ≥2 document khác nhau, hoặc chuỗi suy luận ≥3 unit_id, hoặc phải đối chiếu `validity_timeline.jsonl`.

## 1.6 Dataset Size & Quota

Target: **400 QA** (dao động 300–500 tùy độ khó khi build), Human Review 100%.

| Category | Số lượng |
|---|---:|
| Single-hop Retrieval | 140 |
| Citation | 60 |
| Multi-hop | 60 (≥50% có edges ngữ nghĩa) |
| Cross-document | 50 (≥60% có edges ngữ nghĩa) |
| Legal Validity | 60 |
| Unanswerable | 30 |
| **Tổng** | **400** |

Source distribution: `generated` ~90%, `manual` ~10% (case khó tự nhiên hóa, ví dụ unanswerable tinh vi).

---

# 2. EVALUATION METRICS

Metrics chia thành **3 nhóm**, mỗi nhóm đo một tầng khác nhau của hệ RAG. Không gộp chung — vì điểm yếu ở 1 tầng dễ bị điểm mạnh ở tầng khác che khuất nếu trộn lẫn.

## 2.1 Retrieval Metrics — đo khả năng "tìm đúng evidence"

| Metric | Đo gì |
|---|---|
| Recall@1 / @5 / @10 | Ground-truth chunk (minimal evidence) có xuất hiện trong top-1/5/10 kết quả không |
| MRR (Mean Reciprocal Rank) | Evidence đúng đầu tiên xuất hiện ở vị trí nào (trung bình nghịch đảo rank) — đo tốc độ tìm đúng |
| nDCG@K | Chất lượng ranking có trọng số theo vị trí, phạt nặng nếu evidence đúng bị xếp thấp |
| **Jaccard Similarity (chunk-level)** | `\|retrieved ∩ ground_truth\| / \|retrieved ∪ ground_truth\|` — so tập chunk trả về với tập `ground_truth.chunk_ids` tối thiểu.|

→ Nhóm này hoàn toàn độc lập với generator — đo riêng chất lượng retriever đang test. Recall@K/MRR/nDCG đo "có tìm thấy không", Jaccard đo thêm "có tìm **gọn** không".

## 2.2 Generation Metrics — đo khả năng "trả lời đúng & trung thực dựa trên evidence đã tìm được"

Chọn theo `answer_type` để giảm chi phí — chỉ dùng các metric tự động phù hợp với từng loại câu trả lời.

| Metric | Công thức / công cụ | Áp dụng cho `answer_type` | Đo gì |
|---|---|---|---|
| **Exact Match (EM)** | So khớp chuỗi chính xác (sau chuẩn hóa: bỏ dấu câu, lowercase) giữa câu trả lời và `reference_answer` | `extractive`, `boolean` | Trả lời có khớp tuyệt đối với đáp án hay không — chỉ số cứng, không mơ hồ |
| **Token-level F1 (SQuAD-style)** | Precision/Recall trên tập token chung giữa câu trả lời và `reference_answer`, F1 = 2PR/(P+R) | `extractive` | Trả lời có chứa đúng phần lõi thông tin, kể cả khi diễn đạt khác chút ít |
| **ROUGE-L** | Longest Common Subsequence giữa câu trả lời và `reference_answer` | `abstractive` | Độ trùng khớp về nội dung/cấu trúc câu khi câu trả lời được diễn giải lại |
| **BERTScore (F1)** | Cosine similarity giữa embedding token của câu trả lời và `reference_answer`, dùng model tiếng Việt (`bkai-foundation-models/vietnamese-bi-encoder` hoặc `PhoBERT`) | `abstractive` | Độ tương đồng ngữ nghĩa khi câu chữ khác nhau nhưng ý nghĩa giống nhau (bù cho hạn chế của ROUGE/EM chỉ so khớp bề mặt) |
| **RAGAS Faithfulness** | Tách câu trả lời thành các claim đơn lẻ, dùng NLI/LLM kiểm tra từng claim có được entail bởi context đã retrieve không; điểm = tỷ lệ claim được support | Tất cả | Đo hallucination — câu trả lời có bịa thông tin ngoài context không |
| **RAGAS Context Precision** | Với mỗi vị trí trong context đã retrieve, đánh giá có liên quan đến câu hỏi không, tính theo trọng số vị trí (giống nDCG) | Tất cả | Trong context đã retrieve, bao nhiêu phần thực sự liên quan (không nhiễu) |
| **RAGAS Context Recall** | So khớp từng câu trong `reference_answer`/ground truth có được context đã retrieve "phủ" hay không | Tất cả | Context đã retrieve có đủ để trả lời đúng không (không thiếu) |
| **RAGAS Answer Relevancy** | Sinh ngược lại câu hỏi giả định từ câu trả lời, đo cosine similarity với câu hỏi gốc | Tất cả | Câu trả lời có đi thẳng vào trọng tâm câu hỏi hay lan man/né tránh |

**Quy tắc chọn metric theo `answer_type` (chỉ dùng metric tự động, không dùng metric phụ thuộc mô hình đánh giá):**

```
extractive    → Exact Match + Token F1                         (tự động, rẻ)
boolean       → Exact Match                                     (tự động, rẻ)
abstractive   → ROUGE-L + BERTScore F1                          (tự động, rẻ)
mọi loại      → RAGAS Faithfulness / Context Precision / Context Recall / Answer Relevancy
```

## 2.3 Legal-specific Metrics — đo năng lực đặc thù pháp lý mà metric RAG chung không bắt được

| Metric | Đo gì |
|---|---|
| **Citation Set Jaccard** | `\|cited_units_predicted ∩ cited_units_ground_truth\| / \|cited_units_predicted ∪ cited_units_ground_truth\|` — so **tập** số điều/văn bản được trích dẫn trong câu trả lời với tập ground truth (subset `citation`). Thay thế cách nói chung chung "precision/recall của citation" bằng 1 con số duy nhất, phạt cả trích thiếu lẫn trích thừa/sai |
| **Citation String CER (Character Error Rate)** | Tỷ lệ lỗi ký tự (chèn/xóa/thay thế) giữa chuỗi trích dẫn sinh ra (vd. "Điều 5 Khoản 2 Nghị định 91/2015/NĐ-CP") và chuỗi ground truth, tính ở cấp **ký tự** (không phải từ) | Đo độ chính xác *định dạng* trích dẫn — sai 1 số điều/1 ký tự trong số hiệu văn bản làm sai lệch hoàn toàn ý nghĩa pháp lý dù nội dung câu trả lời đúng. Dùng CER thay WER vì tiếng Việt tách từ mơ hồ (compound word không có ranh giới rõ), CER ở cấp ký tự ổn định hơn, không phụ thuộc tokenizer |
| Multi-hop Success Rate | Tỷ lệ trả lời đúng khi cần kết hợp ≥2 provision (subset `multi_hop`) |
| **Graph Traversal Accuracy** | Trong subset có `edges_used` chứa quan hệ ngữ nghĩa có kiểu (`rel_amends`/`rel_replaces`/`rel_refers_to`), hệ thống có dùng đúng loại quan hệ để đi tới evidence hay chỉ "trúng" nhờ tương đồng ngôn ngữ tình cờ |
| Validity Reasoning Accuracy | Câu trả lời có phản ánh đúng `currency_status` tại `as_of_date` không — không dùng quy định đã bị thay thế/hết hiệu lực (subset `legal_validity`) |
| Unanswerable Detection Accuracy | Tỷ lệ hệ thống từ chối đúng khi câu hỏi không có câu trả lời trong corpus (subset `unanswerable`) |

---

# 3. EVALUATION PIPELINE

## 3.1 End-to-end Evaluation Workflow (đơn giản hóa)

```
Golden Benchmark → Retrieval → Answer Generation → Metric Computation → Evaluation Report
```

Diễn giải từng bước:

1. **Golden Benchmark** — load `benchmark_v2.0.jsonl` (frozen), cùng bộ QA cho mọi hệ thống được test.
2. **Retrieval** — hệ retriever đang test (BM25/Dense/Hybrid/GraphRAG...) chạy trên từng `question`, trả về Top-K chunks.
3. **Answer Generation** — generator (LLM) sinh câu trả lời dựa trên Top-K chunks vừa retrieve.
4. **Metric Computation** — tính đồng thời 3 nhóm metric (2.1, 2.2, 2.3) bằng cách so khớp với `ground_truth` và các metric tự động.
5. **Evaluation Report** — tổng hợp kết quả theo category/difficulty/`edges_used` type, xuất báo cáo (xem mục 4).

## 3.2 Kiến trúc chi tiết

```
┌─────────────────┐
│  benchmark.jsonl │ (frozen, 400 QA)
└────────┬─────────┘
         ▼
┌──────────────────────────┐
│ Retriever (system dưới    │  Top-K (cấu hình, ví dụ K=10 lúc eval thật)
│ test)                     │
└────────┬──────────────────┘
         ▼
┌────────────────────┐     ┌───────────────────────────┐
│ Retrieval Metrics    │     │ Generator (LLM + context)  │
│ (2.1)                 │     │ → candidate_answer          │
└────────────────────┘     └────────┬────────────────┘
                                     ▼
                        ┌───────────────────────────┐
                        │ Automatic Metric          │
                        │ Computation (2.2 + 2.3)   │
                        └────────┬────────────────┘
                                 ▼
                    ┌───────────────────────────┐
                    │ Evaluation Report           │
                    │ theo category/difficulty/   │
                    │ edges_used type              │
                    └───────────────────────────┘
```

## 3.3 Yêu cầu logging mỗi lần chạy

Mỗi run phải ghi lại: `corpus_version`, `benchmark_version`, `retriever_config`, `top_k`, `generator_model`, `timestamp` — để đảm bảo kết quả tái lập được và so sánh công bằng giữa các lần chạy/hệ thống khác nhau.

---

# 4. EVALUATION SCORES

**Nguyên tắc:** kết quả được báo cáo **tách riêng theo từng nhóm metric và từng category** — không gộp thành 1 con số duy nhất theo mặc định. Một điểm tổng dễ che giấu điểm yếu nghiêm trọng ở category rủi ro cao (ví dụ Legal Validity, Cross-document) trong khi điểm trung bình vẫn "trông ổn" nhờ Single-hop dễ đạt điểm cao.

## 4.1 Retrieval Scores

Báo cáo Recall@1/5/10, MRR, nDCG@10 — tổng thể và **breakdown theo category**:

```
                single_hop  citation  multi_hop  cross_doc  legal_val
Recall@10          0.92        0.78      0.61        0.48       0.55
MRR                0.85        0.70      0.52        0.40       0.47
nDCG@10            0.88        0.74      0.58        0.44       0.51
Jaccard (chunk)    0.80        0.65      0.50        0.38       0.44
```

## 4.2 Generation Scores

Báo cáo theo đúng tên metric cụ thể ở mục 2.2 (không gộp thành "Answer Correctness" chung chung), tách theo `answer_type` chiếm ưu thế trong mỗi category — tổng thể và breakdown theo category:

```
                     single_hop  citation  multi_hop  cross_doc  legal_val  unanswer
Exact Match             0.85       0.70        -          -          -          -
Token F1                0.90       0.81       0.72         -          -          -
ROUGE-L                  -          -         0.65       0.55       0.60         -
BERTScore F1              -          -         0.78       0.68       0.71         -
RAGAS Faithfulness      0.95       0.88       0.80       0.66       0.70       0.90
RAGAS Context Precision 0.91       0.83       0.74       0.62       0.69        -
RAGAS Context Recall    0.89       0.80       0.70       0.58       0.65        -
RAGAS Answer Relevancy  0.92       0.85       0.76       0.64       0.70       0.88
```

> Ô "-" nghĩa là metric đó không áp dụng cho category/answer_type tương ứng (ví dụ Single-hop chủ yếu là `extractive` nên không cần ROUGE-L/BERTScore).

## 4.3 Legal-specific Scores

Báo cáo riêng cho subset tương ứng:

```
Citation Set Jaccard        0.72   (subset: citation)
Citation String CER         0.08   (subset: citation — CER càng THẤP càng tốt, khác các metric khác ở trên)
MultiHopSuccessRate         0.68   (subset: multi_hop)
GraphTraversalAccuracy      0.55   (subset: edges_used có quan hệ ngữ nghĩa có kiểu)
ValidityReasoningAccuracy   0.62   (subset: legal_validity)
UnanswerableDetectionAcc    0.85   (subset: unanswerable)
```

> Lưu ý khi đọc báo cáo: **Citation String CER là metric "càng thấp càng tốt"** (đo tỷ lệ lỗi), ngược chiều với tất cả metric khác trong framework này (đều là "càng cao càng tốt") — cần ghi chú rõ trong mọi bảng/dashboard để tránh hiểu nhầm khi so sánh.

## 4.4 Per-category Results (bảng tổng hợp trình bày)

Bảng chính dùng để trình bày/so sánh giữa các hệ thống — mỗi hàng là 1 category, mỗi cột là 1 metric liên quan nhất đến category đó:

| Category | Retrieval (Recall@10) | Generation (Faithfulness) | Legal-specific |
|---|---:|---:|---|
| Single-hop | 0.92 | 0.95 | — |
| Citation | 0.78 | 0.88 | Citation Acc: 0.75 |
| Multi-hop | 0.61 | 0.80 | Multi-hop Success: 0.68 |
| Cross-document | 0.48 | 0.66 | Graph Traversal Acc: 0.55 |
| Legal Validity | 0.55 | 0.70 | Validity Reasoning Acc: 0.62 |
| Unanswerable | — | 0.90 | Detection Acc: 0.85 |

## 4.5 Composite Score — KHÔNG mặc định, chỉ optional

- **Mặc định**: không tính điểm tổng hợp. Báo cáo luôn ở dạng tách riêng theo 4.1–4.4.
- **Nếu cần 1 con số headline** (ví dụ để báo cáo nhanh cho stakeholder không kỹ thuật), có thể tính thêm, nhưng phải đi kèm ngay bảng breakdown chi tiết bên cạnh, không thay thế nó:

```
CompositeScore (optional) =
    0.30 * Recall@10 (retrieval, trung bình các category)
  + 0.30 * Faithfulness
  + 0.20 * AnswerCorrectness
  + 0.10 * CitationAccuracy + GraphTraversalAccuracy (trung bình)
  + 0.10 * UnanswerableDetectionAccuracy
```

- Không dùng composite score để so sánh giữa các phiên bản benchmark khác nhau — chỉ so sánh trong cùng 1 benchmark version (frozen).
- Không dùng composite score làm tiêu chí duy nhất để "pass/fail" 1 hệ thống — luôn xem cùng bảng per-category.

---

# 5. Versioning & Governance

| Sự kiện | Hành động |
|---|---|
| QA sai sau khi freeze | `status: deprecated`, giữ lịch sử, release patch version |
| `validity_timeline.jsonl` cập nhật | Re-check `currency_status` của QA liên quan, đánh dấu `status: needs_review`, không tự sửa `reference_answer` |
| Đổi retriever/chunking của hệ đang test | Không ảnh hưởng benchmark (đã frozen) — chỉ ảnh hưởng kết quả run, ghi rõ config trong report |
| Cần thêm category/mở rộng | Tạo `benchmark_v2.0`, không trộn lẫn vào v1.x |