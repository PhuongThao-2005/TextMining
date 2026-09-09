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
| exact_match | 0.1475 |
| token_f1 | 0.2502 |
| rouge_l | 0.2189 |
| unanswerable_accuracy | 0.8440 |
| context_recall@k | 0.4855 |
| recall@1 | 0.0902 |
| hit@1 | 0.1025 |
| mrr@1 | 0.1025 |
| ndcg@1 | 0.1025 |
| jaccard@1 | 0.0902 |
| recall@5 | 0.3678 |
| hit@5 | 0.4025 |
| mrr@5 | 0.2088 |
| ndcg@5 | 0.2404 |
| jaccard@5 | 0.0820 |
| recall@10 | 0.4855 |
| hit@10 | 0.5325 |
| mrr@10 | 0.2267 |
| ndcg@10 | 0.2813 |
| jaccard@10 | 0.0568 |

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
| recall@1 | 0.0902 |
| hit@1 | 0.1025 |
| mrr@1 | 0.1025 |
| ndcg@1 | 0.1025 |
| jaccard@1 | 0.0902 |
| recall@5 | 0.3678 |
| hit@5 | 0.4025 |
| mrr@5 | 0.2088 |
| ndcg@5 | 0.2404 |
| jaccard@5 | 0.0820 |
| recall@10 | 0.4855 |
| hit@10 | 0.5325 |
| mrr@10 | 0.2267 |
| ndcg@10 | 0.2813 |
| jaccard@10 | 0.0568 |

## By Category

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| citation | 106 | 0.1698 | 0.2664 | 0.2315 | 0.9811 | 0.6453 | 0.0849 | 0.0849 | 0.0849 | 0.0849 | 0.0849 | 0.5160 | 0.5283 | 0.2338 | 0.3019 | 0.1045 | 0.6453 | 0.6509 | 0.2511 | 0.3454 | 0.0665 |
| cross_document | 12 | 0.0000 | 0.3004 | 0.2539 | 0.5833 | 0.2530 | 0.0682 | 0.1818 | 0.1818 | 0.1818 | 0.0682 | 0.1894 | 0.3636 | 0.2227 | 0.1809 | 0.0867 | 0.2530 | 0.5455 | 0.2470 | 0.2080 | 0.0627 |
| legal_validity | 96 | 0.0989 | 0.1600 | 0.1473 | 0.5938 | 0.3791 | 0.0440 | 0.0659 | 0.0659 | 0.0659 | 0.0440 | 0.2674 | 0.3516 | 0.1670 | 0.1710 | 0.0668 | 0.3791 | 0.5055 | 0.1892 | 0.2142 | 0.0536 |
| multi_hop | 21 | 0.1500 | 0.3241 | 0.2686 | 0.9048 | 0.4000 | 0.0250 | 0.0500 | 0.0500 | 0.0500 | 0.0250 | 0.1750 | 0.3000 | 0.1667 | 0.1412 | 0.0760 | 0.4000 | 0.5500 | 0.1974 | 0.2271 | 0.0846 |
| single_hop | 265 | 0.1686 | 0.2761 | 0.2409 | 0.8868 | 0.4680 | 0.1269 | 0.1337 | 0.1337 | 0.1337 | 0.1269 | 0.3634 | 0.3663 | 0.2196 | 0.2544 | 0.0766 | 0.4680 | 0.4709 | 0.2336 | 0.2883 | 0.0488 |

## By Answer Type

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| abstractive | 199 | 0.0000 | 0.3257 | 0.2705 | 0.8492 | 0.4445 | 0.0766 | 0.0854 | 0.0854 | 0.0854 | 0.0766 | 0.3254 | 0.3618 | 0.1817 | 0.2101 | 0.0728 | 0.4445 | 0.4975 | 0.2008 | 0.2524 | 0.0533 |
| boolean | 123 | 0.4797 | 0.0809 | 0.0809 | 0.6504 | 0.4878 | 0.0759 | 0.0976 | 0.0976 | 0.0976 | 0.0759 | 0.3930 | 0.4309 | 0.2154 | 0.2476 | 0.0901 | 0.4878 | 0.5447 | 0.2310 | 0.2811 | 0.0582 |
| extractive | 78 | 0.0000 | 0.3245 | 0.3047 | 0.9487 | 0.5863 | 0.1474 | 0.1538 | 0.1538 | 0.1538 | 0.1474 | 0.4363 | 0.4615 | 0.2675 | 0.3062 | 0.0926 | 0.5863 | 0.6026 | 0.2859 | 0.3553 | 0.0633 |
| unanswerable | 100 | 0.0000 | 0.0000 | 0.0000 | 0.9900 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## By Difficulty

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| easy | 378 | 0.1719 | 0.2646 | 0.2324 | 0.8836 | 0.5330 | 0.0994 | 0.1053 | 0.1053 | 0.1053 | 0.0994 | 0.4171 | 0.4421 | 0.2224 | 0.2660 | 0.0886 | 0.5330 | 0.5614 | 0.2387 | 0.3051 | 0.0579 |
| hard | 1 | 0.0000 | 0.0426 | 0.0426 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| medium | 121 | 0.0877 | 0.2160 | 0.1867 | 0.7190 | 0.3709 | 0.0680 | 0.0965 | 0.0965 | 0.0965 | 0.0680 | 0.2478 | 0.3070 | 0.1768 | 0.1785 | 0.0661 | 0.3709 | 0.4649 | 0.1985 | 0.2244 | 0.0544 |

## Stage Latency

| Stage | Count | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | P95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dense_retrieval | 500 | 740.798 | 737.375 | 711.639 | 800.360 | 770.777 |
| sparse_retrieval | 0 | — | — | — | — | — |
| graph_traversal | 0 | — | — | — | — | — |
| fusion | 0 | — | — | — | — | — |
| reranker | 0 | — | — | — | — | — |
| generation | 500 | 3099.597 | 2730.426 | 1415.777 | 21348.752 | 5106.215 |
| planner_decision | 0 | — | — | — | — | — |
| tool_retrieval | 0 | — | — | — | — | — |
| agent_total | 0 | — | — | — | — | — |
| judge | 0 | — | — | — | — | — |
| serialization | 500 | 0.040 | 0.043 | 0.021 | 0.125 | 0.060 |
| total | 500 | 3841.800 | 3474.691 | 2172.487 | 22080.111 | 5887.308 |

## Failures

- Failed cases: 0
- Artifact: `errors.jsonl`
- No case failures recorded.
