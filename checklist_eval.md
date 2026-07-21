# Checklist for `L_RAG/notebooks/vector_retrieval_eval.ipynb`

## 1. Environment and files

- [ ] Open `L_RAG/notebooks/vector_retrieval_eval.ipynb` in Google Colab.
- [ ] Set Colab runtime to GPU: `Runtime > Change runtime type > GPU`.
- [ ] Run the setup cell that removes/clones the repo.
- [ ] Mount Google Drive successfully.
- [ ] Install dependencies:
  - `faiss-gpu`
  - `sentence-transformers`
  - `pandas`
  - `openai` if intent extraction is enabled.

## 2. Verify paths before running

Check these paths in the configuration cell:

```python
QA_PATH = Path("/content/drive/Shareddrives/[Text Mining] - Project/Benchmark/qa_final.jsonl")
INDEX_DIR = Path("/content/drive/Shareddrives/[Text Mining] - Project/faiss_index")
OUT_DIR = Path("/content/drive/Shareddrives/[Text Mining] - Project/Benchmark/eval_retrieval_only")
```

Before the presentation run, confirm:

- [ ] `qa_final.jsonl` exists at `QA_PATH`.
- [ ] `INDEX_DIR` exists.
- [ ] `INDEX_DIR` contains `index.faiss`.
- [ ] `INDEX_DIR` contains `payloads.jsonl`.
- [ ] `OUT_DIR` points to the folder where you want to save results.

## 3. Use the correct mode for final results

For a quick smoke test only:

```python
SAMPLE_LIMIT = 10
DEV_HASHING = True
```

For final results to show the lecturer:

```python
SAMPLE_LIMIT = None
DEV_HASHING = False
```

Checklist:

- [ ] Do not present results from `DEV_HASHING = True`.
- [ ] Do not present final numbers from `SAMPLE_LIMIT = 10`.
- [ ] Use `DEV_HASHING = False` for real FAISS retrieval.
- [ ] Use `SAMPLE_LIMIT = None` for the full eligible benchmark.

## 4. Confirm retrieval configuration

Check these values:

```python
TOP_K_LIST = [1, 5, 10]
MODEL_NAME = "intfloat/multilingual-e5-large"
SCORE_THRESHOLD = 0.3
EXPAND_UNITS = True
EMBEDDER_DEVICE = "auto"
```

Checklist:

- [ ] `TOP_K_LIST` is `[1, 5, 10]`.
- [ ] Embedding model is `intfloat/multilingual-e5-large`.
- [ ] Score threshold is documented.
- [ ] Device is `auto` or `cuda` if GPU is available.

## 5. Decide intent extraction setting

The notebook has optional query rewriting:

```python
INTENT_EXTRACTION_ENABLED = True
```

If using intent extraction:

- [ ] Add `INTENT_LLM_API_KEY` in Colab Secrets or environment variables.
- [ ] Confirm the selected model, e.g. `gpt-4o-mini`.
- [ ] Mention in the presentation that questions were rewritten before retrieval.

If not using intent extraction:

```python
INTENT_EXTRACTION_ENABLED = False
```

- [ ] Mention that raw benchmark questions were sent directly to the retriever.

## 6. Run notebook cells in order

Run from top to bottom and check each stage:

- [ ] Environment setup completed.
- [ ] Configuration printed correctly.
- [ ] QA benchmark loaded successfully.
- [ ] Eligibility summary printed.
- [ ] Retriever built successfully.
- [ ] Intent extraction either works or is disabled.
- [ ] Retrieval and scoring loop finishes.
- [ ] Overall metrics table is displayed.
- [ ] Breakdown tables are displayed.
- [ ] Per-case results table is displayed.

Important outputs to look for:

```text
Eligibility summary
```

```text
Retriever ready (store=faiss, device=...)
```

```text
Evaluated X case(s); error_count=0
```

```text
=== VECTOR-ONLY retrieval evaluation — run summary ===
```

## 7. Validate results before presenting

- [ ] `error_count` should be `0`, or explain any errors.
- [ ] Number of evaluated cases should match the full eligible benchmark if `SAMPLE_LIMIT = None`.
- [ ] Skipped unanswerable questions are reported.
- [ ] Skipped missing-ground-truth questions are reported.
- [ ] Overall metrics table is visible.
- [ ] Breakdown by category is visible.
- [ ] Breakdown by difficulty is visible.
- [ ] Breakdown by answer type is visible.

## 8. Save artifacts

In the final persistence cell, set:

```python
PERSIST = True
```

Then rerun that cell.

Expected saved files:

- [ ] `retrieval_cases.jsonl`
- [ ] `retrieval_metrics.json`

These should be saved under:

```python
OUT_DIR
```

Keep these files for backup and reporting.

## 9. Prepare result tables for slides

Include these values:

- [ ] Total benchmark rows.
- [ ] Number of evaluated eligible questions.
- [ ] Skipped unanswerable count.
- [ ] Skipped missing-ground-truth count.
- [ ] Error count.
- [ ] Hit@1.
- [ ] Hit@5.
- [ ] Hit@10.
- [ ] Recall@1.
- [ ] Recall@5.
- [ ] Recall@10.
- [ ] MRR@1 / MRR@5 / MRR@10 if shown by the notebook.
- [ ] Metrics by category.
- [ ] Metrics by difficulty.
- [ ] Metrics by answer type.

## 10. Prepare explanation for lecturer

Say clearly:

- [ ] This notebook evaluates **vector-only retrieval**.
- [ ] It uses a local **FAISS index**.
- [ ] It uses a SQLite/payload cache through `SQLitePayloadFaissVectorStore`.
- [ ] It does **not** use Qdrant.
- [ ] It does **not** use knowledge-graph expansion.
- [ ] It does **not** use hybrid fusion.
- [ ] It evaluates retrieval only, not final answer generation.

Suggested explanation:

> We evaluate the vector-only retrieval module using the frozen QA benchmark. For each eligible question, the system retrieves candidate legal text chunks from a FAISS vector index. The retrieved chunk IDs are compared with the ground-truth chunk IDs, and we report retrieval metrics at Top-1, Top-5, and Top-10.

## 11. Prepare error analysis examples

From the per-case dataframe:

- [ ] Pick 1–2 successful retrieval examples.
- [ ] Pick 1–2 failed retrieval examples.
- [ ] For each example, show:
  - question,
  - retrieval query,
  - ground-truth chunk IDs,
  - retrieved chunk IDs,
  - whether Hit@K succeeded.

Possible failure explanations:

- semantic mismatch between question and legal text,
- question needs broader context,
- similar legal provisions confuse the vector retriever,
- ground-truth chunk is phrased differently from the question,
- vector-only retrieval does not use graph/legal-structure information.

## 12. Final presentation checklist

- [ ] Notebook has been rerun cleanly from top to bottom.
- [ ] `DEV_HASHING = False`.
- [ ] `SAMPLE_LIMIT = None`.
- [ ] FAISS index is loaded successfully.
- [ ] QA benchmark path is correct.
- [ ] Intent extraction setting is documented.
- [ ] `error_count` is checked.
- [ ] Metrics are saved or screenshotted.
- [ ] Result artifacts are persisted.
- [ ] You can explain Hit@K, Recall@K, and MRR@K.
- [ ] You can explain why this is retrieval-only evaluation.
- [ ] You have at least one success case and one failure case ready for discussion.
