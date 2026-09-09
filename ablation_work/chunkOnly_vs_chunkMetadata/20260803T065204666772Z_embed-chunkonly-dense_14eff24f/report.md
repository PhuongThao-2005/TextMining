# End-to-End RAG Evaluation Report

- QA path: `/kaggle/input/datasets/phuongthao205/qa-legalrag/Benchmark/qa_final.jsonl`
- Total input: 500
- Successful/evaluated: 500
- Failed: 0
- Skipped: 0
- Quality metric denominator: per metric, excluding non-applicable successful cases
- Latency denominator: cases with a recorded value for each stage
- Generator: `gpt-4o-mini`
- Retrieval top-k: 10

## Overall

| Metric | Value |
| --- | ---: |
| exact_match | 0.1450 |
| token_f1 | 0.2491 |
| rouge_l | 0.2195 |
| unanswerable_accuracy | 0.8280 |
| context_recall@k | 0.4847 |
| recall@1 | 0.1486 |
| hit@1 | 0.1650 |
| mrr@1 | 0.1650 |
| ndcg@1 | 0.1650 |
| jaccard@1 | 0.1486 |
| recall@5 | 0.3903 |
| hit@5 | 0.4400 |
| mrr@5 | 0.2736 |
| ndcg@5 | 0.2901 |
| jaccard@5 | 0.0882 |
| recall@10 | 0.4847 |
| hit@10 | 0.5350 |
| mrr@10 | 0.2861 |
| ndcg@10 | 0.3221 |
| jaccard@10 | 0.0567 |

## Metric Denominators

| Metric | Cases |
| --- | ---: |
| exact_match | 400 |
| token_f1 | 400 |
| rouge_l | 400 |
| unanswerable_accuracy | 500 |
| context_recall@k | 400 |
| recall@1 | 400 |
| hit@1 | 400 |
| mrr@1 | 400 |
| ndcg@1 | 400 |
| jaccard@1 | 400 |
| recall@5 | 400 |
| hit@5 | 400 |
| mrr@5 | 400 |
| ndcg@5 | 400 |
| jaccard@5 | 400 |
| recall@10 | 400 |
| hit@10 | 400 |
| mrr@10 | 400 |
| ndcg@10 | 400 |
| jaccard@10 | 400 |

## Retrieval Metrics

| Metric | Value |
| --- | ---: |
| recall@1 | 0.1486 |
| hit@1 | 0.1650 |
| mrr@1 | 0.1650 |
| ndcg@1 | 0.1650 |
| jaccard@1 | 0.1486 |
| recall@5 | 0.3903 |
| hit@5 | 0.4400 |
| mrr@5 | 0.2736 |
| ndcg@5 | 0.2901 |
| jaccard@5 | 0.0882 |
| recall@10 | 0.4847 |
| hit@10 | 0.5350 |
| mrr@10 | 0.2861 |
| ndcg@10 | 0.3221 |
| jaccard@10 | 0.0567 |

## By Category

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| citation | 106 | 0.1604 | 0.2494 | 0.2197 | 0.9151 | 0.6934 | 0.1981 | 0.1981 | 0.1981 | 0.1981 | 0.1981 | 0.5472 | 0.5472 | 0.3393 | 0.3916 | 0.1094 | 0.6934 | 0.6981 | 0.3592 | 0.4389 | 0.0697 |
| cross_document | 12 | 0.0000 | 0.3464 | 0.3171 | 0.7500 | 0.3061 | 0.0864 | 0.2727 | 0.2727 | 0.2727 | 0.0864 | 0.2833 | 0.5455 | 0.3939 | 0.2733 | 0.1293 | 0.3061 | 0.5455 | 0.3939 | 0.2845 | 0.0798 |
| legal_validity | 96 | 0.1209 | 0.1496 | 0.1394 | 0.6042 | 0.4011 | 0.0641 | 0.0879 | 0.0879 | 0.0879 | 0.0641 | 0.2711 | 0.4066 | 0.2048 | 0.1934 | 0.0804 | 0.4011 | 0.5165 | 0.2193 | 0.2406 | 0.0624 |
| multi_hop | 21 | 0.2500 | 0.2778 | 0.2237 | 0.8571 | 0.2083 | 0.0417 | 0.1000 | 0.1000 | 0.1000 | 0.0417 | 0.1917 | 0.3500 | 0.1917 | 0.1443 | 0.0660 | 0.2083 | 0.4000 | 0.1967 | 0.1511 | 0.0402 |
| single_hop | 265 | 0.1453 | 0.2919 | 0.2551 | 0.8755 | 0.4438 | 0.1793 | 0.1860 | 0.1860 | 0.1860 | 0.1793 | 0.3866 | 0.3953 | 0.2714 | 0.2966 | 0.0793 | 0.4438 | 0.4593 | 0.2800 | 0.3156 | 0.0461 |

## By Answer Type

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| abstractive | 199 | 0.0000 | 0.3226 | 0.2697 | 0.8141 | 0.4508 | 0.1296 | 0.1457 | 0.1457 | 0.1457 | 0.1296 | 0.3582 | 0.4020 | 0.2474 | 0.2640 | 0.0804 | 0.4508 | 0.4925 | 0.2586 | 0.2949 | 0.0525 |
| boolean | 123 | 0.4715 | 0.0796 | 0.0796 | 0.6667 | 0.4810 | 0.1558 | 0.1789 | 0.1789 | 0.1789 | 0.1558 | 0.3767 | 0.4553 | 0.2813 | 0.2852 | 0.0914 | 0.4810 | 0.5610 | 0.2952 | 0.3213 | 0.0608 |
| extractive | 78 | 0.0000 | 0.3287 | 0.3121 | 0.9231 | 0.5769 | 0.1859 | 0.1923 | 0.1923 | 0.1923 | 0.1859 | 0.4936 | 0.5128 | 0.3284 | 0.3641 | 0.1031 | 0.5769 | 0.6026 | 0.3421 | 0.3931 | 0.0609 |
| unanswerable | 100 | 0.0000 | 0.0000 | 0.0000 | 0.9800 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## By Difficulty

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| easy | 378 | 0.1614 | 0.2652 | 0.2353 | 0.8730 | 0.5515 | 0.1743 | 0.1825 | 0.1825 | 0.1825 | 0.1743 | 0.4415 | 0.4667 | 0.2963 | 0.3265 | 0.0947 | 0.5515 | 0.5754 | 0.3111 | 0.3635 | 0.0605 |
| hard | 1 | 0.0000 | 0.1176 | 0.1176 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | 121 | 0.1053 | 0.2100 | 0.1808 | 0.6942 | 0.3219 | 0.0858 | 0.1228 | 0.1228 | 0.1228 | 0.0858 | 0.2656 | 0.3772 | 0.2193 | 0.2014 | 0.0728 | 0.3219 | 0.4386 | 0.2263 | 0.2216 | 0.0478 |

## Stage Latency

| Stage | Count | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | P95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dense_retrieval | 500 | 752.561 | 747.102 | 717.454 | 1445.978 | 784.023 |
| sparse_retrieval | 0 | — | — | — | — | — |
| graph_traversal | 0 | — | — | — | — | — |
| fusion | 0 | — | — | — | — | — |
| reranker | 0 | — | — | — | — | — |
| generation | 500 | 3129.573 | 2732.662 | 1194.321 | 22775.862 | 5003.683 |
| planner_decision | 0 | — | — | — | — | — |
| tool_retrieval | 0 | — | — | — | — | — |
| agent_total | 0 | — | — | — | — | — |
| judge | 0 | — | — | — | — | — |
| serialization | 500 | 0.040 | 0.042 | 0.021 | 0.278 | 0.060 |
| total | 500 | 3883.530 | 3479.652 | 1940.298 | 23544.010 | 5756.641 |

## Failures

- Failed cases: 0
- Artifact: `errors.jsonl`
- No case failures recorded.
