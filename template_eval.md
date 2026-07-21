# Evaluation Results Template

Use this template after running `L_RAG/notebooks/vector_retrieval_eval.ipynb`.

## 1. Run information

- **Notebook**: `L_RAG/notebooks/vector_retrieval_eval.ipynb`
- **Run ID**: 
- **Date / Time**: 
- **Runner**: 
- **Environment**: Colab / local / other
- **GPU used**: Yes / No

## 2. Configuration

- **QA_PATH**: 
- **INDEX_DIR**: 
- **OUT_DIR**: 
- **MODEL_NAME**: `intfloat/multilingual-e5-large`
- **TOP_K_LIST**: `[1, 5, 10]`
- **SCORE_THRESHOLD**: `0.3`
- **EXPAND_UNITS**: `True / False`
- **DEV_HASHING**: `True / False`
- **SAMPLE_LIMIT**: 
- **Intent extraction enabled**: `True / False`
- **Intent LLM model**: 

## 3. Dataset summary

- **Total benchmark rows**: 
- **Evaluated rows**: 
- **Skipped unanswerable**: 
- **Skipped missing ground truth**: 
- **Error count**: 

## 4. Overall metrics

| Metric | Value |
| --- | --- |
| Hit@1 |  |
| Hit@5 |  |
| Hit@10 |  |
| Recall@1 |  |
| Recall@5 |  |
| Recall@10 |  |
| MRR@1 |  |
| MRR@5 |  |
| MRR@10 |  |

## 5. Breakdown by category

| Category | Metric summary |
| --- | --- |
|  |  |

## 6. Breakdown by difficulty

| Difficulty | Metric summary |
| --- | --- |
|  |  |

## 7. Breakdown by answer type

| Answer type | Metric summary |
| --- | --- |
|  |  |

## 8. Selected example successes

### Example 1

- **qa_id**: 
- **Question**: 
- **Retrieval query**: 
- **Ground-truth chunk IDs**: 
- **Retrieved chunk IDs**: 
- **Hit@1 / Hit@5 / Hit@10**: 
- **Comment**: 

### Example 2

- **qa_id**: 
- **Question**: 
- **Retrieval query**: 
- **Ground-truth chunk IDs**: 
- **Retrieved chunk IDs**: 
- **Hit@1 / Hit@5 / Hit@10**: 
- **Comment**: 

## 9. Selected example failures

### Example 1

- **qa_id**: 
- **Question**: 
- **Retrieval query**: 
- **Ground-truth chunk IDs**: 
- **Retrieved chunk IDs**: 
- **Error / failure reason**: 
- **Comment**: 

### Example 2

- **qa_id**: 
- **Question**: 
- **Retrieval query**: 
- **Ground-truth chunk IDs**: 
- **Retrieved chunk IDs**: 
- **Error / failure reason**: 
- **Comment**: 

## 10. Lecturer-ready summary

Write 3–5 sentences summarizing the run:

> 

## 11. Key takeaway

- **Main result**: 
- **Main limitation**: 
- **Recommended next step**: 

## 12. Attachments / artifacts

- [ ] `retrieval_cases.jsonl`
- [ ] `retrieval_metrics.json`
- [ ] Screenshot of overall metrics
- [ ] Screenshot of per-case table
- [ ] Screenshot of breakdown tables
