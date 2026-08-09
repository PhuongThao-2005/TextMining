# End-to-End RAG Evaluation Report

- QA path: `/kaggle/input/datasets/phuongthao205/qa-legalrag/Benchmark/qa_final.jsonl`
- Total input: 2
- Successful/evaluated: 2
- Failed: 0
- Skipped: 0
- Quality metric denominator: per metric, excluding non-applicable successful cases
- Latency denominator: cases with a recorded value for each stage
- Generator: `gpt-4o-mini`
- Retrieval top-k: 5

## Overall

| Metric | Value |
| --- | ---: |
| exact_match | 0.0000 |
| token_f1 | 0.1408 |
| rouge_l | 0.1408 |
| unanswerable_accuracy | 1.0000 |
| context_recall@k | 0.0000 |
| recall@1 | 0.0000 |
| hit@1 | 0.0000 |
| mrr@1 | 0.0000 |
| ndcg@1 | 0.0000 |
| jaccard@1 | 0.0000 |
| recall@5 | 0.0000 |
| hit@5 | 0.0000 |
| mrr@5 | 0.0000 |
| ndcg@5 | 0.0000 |
| jaccard@5 | 0.0000 |
| recall@10 | 0.0000 |
| hit@10 | 0.0000 |
| mrr@10 | 0.0000 |
| ndcg@10 | 0.0000 |
| jaccard@10 | 0.0000 |

## Metric Denominators

| Metric | Cases |
| --- | ---: |
| exact_match | 1 |
| token_f1 | 1 |
| rouge_l | 1 |
| unanswerable_accuracy | 2 |
| context_recall@k | 1 |
| recall@1 | 1 |
| hit@1 | 1 |
| mrr@1 | 1 |
| ndcg@1 | 1 |
| jaccard@1 | 1 |
| recall@5 | 1 |
| hit@5 | 1 |
| mrr@5 | 1 |
| ndcg@5 | 1 |
| jaccard@5 | 1 |
| recall@10 | 1 |
| hit@10 | 1 |
| mrr@10 | 1 |
| ndcg@10 | 1 |
| jaccard@10 | 1 |

## Retrieval Metrics

| Metric | Value |
| --- | ---: |
| recall@1 | 0.0000 |
| hit@1 | 0.0000 |
| mrr@1 | 0.0000 |
| ndcg@1 | 0.0000 |
| jaccard@1 | 0.0000 |
| recall@5 | 0.0000 |
| hit@5 | 0.0000 |
| mrr@5 | 0.0000 |
| ndcg@5 | 0.0000 |
| jaccard@5 | 0.0000 |
| recall@10 | 0.0000 |
| hit@10 | 0.0000 |
| mrr@10 | 0.0000 |
| ndcg@10 | 0.0000 |
| jaccard@10 | 0.0000 |

## By Category

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| citation | 1 | 0.0000 | 0.1408 | 0.1408 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| single_hop | 1 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## By Answer Type

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| extractive | 1 | 0.0000 | 0.1408 | 0.1408 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| unanswerable | 1 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## By Difficulty

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| easy | 2 | 0.0000 | 0.1408 | 0.1408 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Stage Latency

| Stage | Count | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | P95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dense_retrieval | 2 | 1321.245 | 1321.245 | 819.748 | 1822.743 | 1822.743 |
| sparse_retrieval | 2 | 129487.370 | 129487.370 | 127323.020 | 131651.720 | 131651.720 |
| graph_traversal | 2 | 2.053 | 2.053 | 2.044 | 2.061 | 2.061 |
| fusion | 2 | 0.079 | 0.079 | 0.070 | 0.088 | 0.088 |
| reranker | 2 | 269.129 | 269.129 | 214.413 | 323.845 | 323.845 |
| generation | 2 | 3487.184 | 3487.184 | 3229.549 | 3744.818 | 3744.818 |
| planner_decision | 0 | — | — | — | — | — |
| tool_retrieval | 0 | — | — | — | — | — |
| agent_total | 0 | — | — | — | — | — |
| judge | 0 | — | — | — | — | — |
| serialization | 2 | 0.045 | 0.045 | 0.043 | 0.047 | 0.047 |
| total | 2 | 134568.850 | 134568.850 | 131590.950 | 137546.750 | 137546.750 |

## Failures

- Failed cases: 0
- Artifact: `errors.jsonl`
- No case failures recorded.
