# End-to-End RAG Evaluation Report

- QA path: `/kaggle/input/datasets/phuongthao205/qa-legalrag/Benchmark/qa_final.jsonl`
- Total input: 500
- Successful/evaluated: 334
- Failed: 166
- Skipped: 0
- Quality metric denominator: per metric, excluding non-applicable successful cases
- Latency denominator: cases with a recorded value for each stage
- Generator: `deepseek-v3.1-thinking`
- Retrieval top-k: 10

## Overall

| Metric | Value |
| --- | ---: |
| exact_match | 0.2157 |
| token_f1 | 0.1762 |
| rouge_l | 0.1514 |
| unanswerable_accuracy | 0.9042 |
| context_recall@k | 0.3928 |
| recall@1 | 0.1474 |
| precision@1 | 0.1647 |
| hit@1 | 0.1647 |
| mrr@1 | 0.1647 |
| ndcg@1 | 0.1647 |
| jaccard@1 | 0.1474 |
| recall@5 | 0.3150 |
| precision@5 | 0.0698 |
| hit@5 | 0.3333 |
| mrr@5 | 0.2259 |
| ndcg@5 | 0.2405 |
| jaccard@5 | 0.0681 |
| recall@10 | 0.3928 |
| precision@10 | 0.0443 |
| hit@10 | 0.4078 |
| mrr@10 | 0.2361 |
| ndcg@10 | 0.2668 |
| jaccard@10 | 0.0438 |

## Metric Denominators

| Metric | Cases |
| --- | ---: |
| exact_match | 255 |
| token_f1 | 255 |
| rouge_l | 255 |
| unanswerable_accuracy | 334 |
| context_recall@k | 255 |
| recall@1 | 255 |
| precision@1 | 255 |
| hit@1 | 255 |
| mrr@1 | 255 |
| ndcg@1 | 255 |
| jaccard@1 | 255 |
| recall@5 | 255 |
| precision@5 | 255 |
| hit@5 | 255 |
| mrr@5 | 255 |
| ndcg@5 | 255 |
| jaccard@5 | 255 |
| recall@10 | 255 |
| precision@10 | 255 |
| hit@10 | 255 |
| mrr@10 | 255 |
| ndcg@10 | 255 |
| jaccard@10 | 255 |

## Retrieval Metrics

| Metric | Value |
| --- | ---: |
| recall@1 | 0.1474 |
| precision@1 | 0.1647 |
| hit@1 | 0.1647 |
| mrr@1 | 0.1647 |
| ndcg@1 | 0.1647 |
| jaccard@1 | 0.1474 |
| recall@5 | 0.3150 |
| precision@5 | 0.0698 |
| hit@5 | 0.3333 |
| mrr@5 | 0.2259 |
| ndcg@5 | 0.2405 |
| jaccard@5 | 0.0681 |
| recall@10 | 0.3928 |
| precision@10 | 0.0443 |
| hit@10 | 0.4078 |
| mrr@10 | 0.2361 |
| ndcg@10 | 0.2668 |
| jaccard@10 | 0.0438 |

## By Category

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | precision@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | precision@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | precision@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| citation | 83 | 0.1084 | 0.1739 | 0.1521 | 0.9036 | 0.4759 | 0.1988 | 0.2048 | 0.2048 | 0.2048 | 0.2048 | 0.1988 | 0.3675 | 0.0747 | 0.3735 | 0.2689 | 0.2903 | 0.0743 | 0.4759 | 0.0482 | 0.4819 | 0.2844 | 0.3264 | 0.0481 |
| cross_document | 9 | 0.0000 | 0.2004 | 0.1654 | 0.6667 | 0.0625 | 0.0312 | 0.1250 | 0.1250 | 0.1250 | 0.1250 | 0.0312 | 0.0625 | 0.0500 | 0.1250 | 0.1250 | 0.0796 | 0.0357 | 0.0625 | 0.0250 | 0.1250 | 0.1250 | 0.0796 | 0.0208 |
| legal_validity | 31 | 0.3462 | 0.1121 | 0.0977 | 0.6774 | 0.3462 | 0.1154 | 0.1154 | 0.1154 | 0.1154 | 0.1154 | 0.1154 | 0.3077 | 0.0615 | 0.3077 | 0.1679 | 0.2019 | 0.0615 | 0.3462 | 0.0346 | 0.3462 | 0.1744 | 0.2156 | 0.0346 |
| multi_hop | 18 | 0.2222 | 0.2090 | 0.1761 | 0.9444 | 0.2500 | 0.1204 | 0.2222 | 0.2222 | 0.2222 | 0.2222 | 0.1204 | 0.1389 | 0.0556 | 0.2778 | 0.2407 | 0.1548 | 0.0442 | 0.2500 | 0.0556 | 0.3889 | 0.2579 | 0.2036 | 0.0510 |
| single_hop | 193 | 0.2750 | 0.1851 | 0.1580 | 0.9482 | 0.3889 | 0.1306 | 0.1417 | 0.1417 | 0.1417 | 0.1417 | 0.1306 | 0.3236 | 0.0717 | 0.3333 | 0.2132 | 0.2379 | 0.0709 | 0.3889 | 0.0433 | 0.3917 | 0.2202 | 0.2587 | 0.0432 |

## By Answer Type

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | precision@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | precision@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | precision@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| abstractive | 120 | 0.0000 | 0.2358 | 0.1946 | 0.8417 | 0.3583 | 0.0993 | 0.1167 | 0.1167 | 0.1167 | 0.1167 | 0.0993 | 0.2875 | 0.0633 | 0.3083 | 0.1856 | 0.2019 | 0.0610 | 0.3583 | 0.0408 | 0.3750 | 0.1957 | 0.2273 | 0.0400 |
| boolean | 77 | 0.7143 | 0.0469 | 0.0469 | 0.8831 | 0.4502 | 0.1710 | 0.1948 | 0.1948 | 0.1948 | 0.1948 | 0.1710 | 0.3420 | 0.0779 | 0.3636 | 0.2554 | 0.2683 | 0.0763 | 0.4502 | 0.0519 | 0.4675 | 0.2686 | 0.3039 | 0.0515 |
| extractive | 58 | 0.0000 | 0.2244 | 0.2009 | 0.9310 | 0.3879 | 0.2155 | 0.2241 | 0.2241 | 0.2241 | 0.2241 | 0.2155 | 0.3362 | 0.0724 | 0.3448 | 0.2701 | 0.2833 | 0.0718 | 0.3879 | 0.0414 | 0.3966 | 0.2764 | 0.2994 | 0.0412 |
| unanswerable | 79 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## By Difficulty

| Group | Count | exact_match | token_f1 | rouge_l | unanswerable_accuracy | context_recall@k | recall@1 | precision@1 | hit@1 | mrr@1 | ndcg@1 | jaccard@1 | recall@5 | precision@5 | hit@5 | mrr@5 | ndcg@5 | jaccard@5 | recall@10 | precision@10 | hit@10 | mrr@10 | ndcg@10 | jaccard@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| easy | 271 | 0.2335 | 0.1766 | 0.1535 | 0.9262 | 0.4247 | 0.1684 | 0.1777 | 0.1777 | 0.1777 | 0.1777 | 0.1684 | 0.3367 | 0.0721 | 0.3452 | 0.2387 | 0.2601 | 0.0715 | 0.4247 | 0.0457 | 0.4315 | 0.2505 | 0.2892 | 0.0455 |
| medium | 63 | 0.1552 | 0.1748 | 0.1444 | 0.8095 | 0.2845 | 0.0761 | 0.1207 | 0.1207 | 0.1207 | 0.1207 | 0.0761 | 0.2414 | 0.0621 | 0.2931 | 0.1822 | 0.1738 | 0.0566 | 0.2845 | 0.0397 | 0.3276 | 0.1871 | 0.1910 | 0.0378 |

## Stage Latency

| Stage | Count | Mean (ms) | Median (ms) | Min (ms) | Max (ms) | P95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dense_retrieval | 500 | 1142.852 | 1119.575 | 941.917 | 2113.958 | 1350.841 |
| sparse_retrieval | 0 | — | — | — | — | — |
| graph_traversal | 500 | 13.498 | 12.178 | 2.354 | 71.145 | 24.518 |
| fusion | 500 | 0.225 | 0.217 | 0.135 | 0.783 | 0.304 |
| reranker | 500 | 8017.298 | 8121.771 | 4119.925 | 15911.191 | 8617.240 |
| generation | 334 | 20380.438 | 17093.279 | 2440.807 | 99329.018 | 49654.310 |
| planner_decision | 0 | — | — | — | — | — |
| tool_retrieval | 0 | — | — | — | — | — |
| agent_total | 0 | — | — | — | — | — |
| judge | 0 | — | — | — | — | — |
| serialization | 334 | 0.068 | 0.067 | 0.028 | 0.248 | 0.122 |
| total | 500 | 23284.969 | 19229.874 | 6735.601 | 108539.685 | 50242.243 |

## Failures

- Failed cases: 166
- Artifact: `errors.jsonl`

| Stage | Count |
| --- | ---: |
| generation | 166 |
