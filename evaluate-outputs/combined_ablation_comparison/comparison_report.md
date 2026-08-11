# Combined Ablation Comparison

This report combines DenseOnly/DenseGraph and HybridOnly/HybridGraph outputs.

## Dataset Check

- Dense run rows: 1000
- Hybrid run rows: 1000
- Unique QA IDs: 500
- Answerable QA: 400
- Unanswerable QA: 100

## How To Read

- Use `answerable_only` for retrieval quality conclusions.
- Use `unanswerable_only` mainly for fallback/abstention behavior.
- Positive latency delta means the left mode is slower.

## Main Metrics

### all_cases

| Mode | recall@10 | hit@10 | mrr@10 | ndcg@10 | precision@10 | exact_match | token_f1 | rouge_l | unanswerable_accuracy | total_latency_sec | median_total_latency_sec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DenseOnly | 0.3884 | 0.4260 | 0.1813 | 0.2250 | 0.0464 | 0.0000 | 0.2081 | 0.1847 | 0.3800 | 5.9812 | 5.4827 |
| DenseGraph | 0.2892 | 0.3120 | 0.1636 | 0.1899 | 0.0340 | 0.0000 | 0.2149 | 0.1904 | 0.4100 | 5.5314 | 4.9980 |
| HybridOnly | 0.3405 | 0.3720 | 0.1802 | 0.2110 | 0.0394 | 0.0000 | 0.2138 | 0.1911 | 0.3800 | 31.6572 | 31.5385 |
| HybridGraph | 0.2461 | 0.2600 | 0.1610 | 0.1782 | 0.0292 | 0.0000 | 0.2260 | 0.2008 | 0.4700 | 31.3689 | 31.1795 |

### answerable_only

| Mode | recall@10 | hit@10 | mrr@10 | ndcg@10 | precision@10 | exact_match | token_f1 | rouge_l | unanswerable_accuracy | total_latency_sec | median_total_latency_sec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DenseOnly | 0.4855 | 0.5325 | 0.2267 | 0.2813 | 0.0580 | 0.0000 | 0.1949 | 0.1665 |  | 5.8811 | 5.4269 |
| DenseGraph | 0.3615 | 0.3900 | 0.2045 | 0.2374 | 0.0425 | 0.0000 | 0.1987 | 0.1691 |  | 5.4877 | 4.9338 |
| HybridOnly | 0.4257 | 0.4650 | 0.2252 | 0.2638 | 0.0492 | 0.0000 | 0.1990 | 0.1719 |  | 31.7189 | 31.5906 |
| HybridGraph | 0.3076 | 0.3250 | 0.2012 | 0.2228 | 0.0365 | 0.0000 | 0.2014 | 0.1710 |  | 31.4114 | 31.2267 |

### unanswerable_only

| Mode | recall@10 | hit@10 | mrr@10 | ndcg@10 | precision@10 | exact_match | token_f1 | rouge_l | unanswerable_accuracy | total_latency_sec | median_total_latency_sec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DenseOnly | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2613 | 0.2578 | 0.3800 | 6.3816 | 6.0672 |
| DenseGraph | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2797 | 0.2752 | 0.4100 | 5.7060 | 5.1045 |
| HybridOnly | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2733 | 0.2681 | 0.3800 | 31.4101 | 31.3513 |
| HybridGraph | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.3245 | 0.3201 | 0.4700 | 31.1992 | 31.0995 |

## Deltas

Positive means the left mode is higher than the right mode. For latency, positive means slower.

### all_cases

| Comparison | recall@10_delta | hit@10_delta | mrr@10_delta | ndcg@10_delta | precision@10_delta | exact_match_delta | token_f1_delta | rouge_l_delta | unanswerable_accuracy_delta | total_latency_sec_delta | median_total_latency_sec_delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DenseGraph_minus_DenseOnly | -0.0992 | -0.1140 | -0.0177 | -0.0351 | -0.0124 | 0.0000 | 0.0067 | 0.0056 | 0.0300 | -0.4498 | -0.4847 |
| HybridGraph_minus_HybridOnly | -0.0945 | -0.1120 | -0.0192 | -0.0328 | -0.0102 | 0.0000 | 0.0122 | 0.0097 | 0.0900 | -0.2882 | -0.3590 |
| HybridOnly_minus_DenseOnly | -0.0478 | -0.0540 | -0.0012 | -0.0140 | -0.0070 | 0.0000 | 0.0057 | 0.0064 | 0.0000 | 25.6760 | 26.0558 |
| HybridGraph_minus_DenseGraph | -0.0431 | -0.0520 | -0.0026 | -0.0117 | -0.0048 | 0.0000 | 0.0111 | 0.0105 | 0.0600 | 25.8375 | 26.1815 |

### answerable_only

| Comparison | recall@10_delta | hit@10_delta | mrr@10_delta | ndcg@10_delta | precision@10_delta | exact_match_delta | token_f1_delta | rouge_l_delta | unanswerable_accuracy_delta | total_latency_sec_delta | median_total_latency_sec_delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DenseGraph_minus_DenseOnly | -0.1240 | -0.1425 | -0.0222 | -0.0439 | -0.0155 | 0.0000 | 0.0038 | 0.0027 |  | -0.3934 | -0.4931 |
| HybridGraph_minus_HybridOnly | -0.1181 | -0.1400 | -0.0240 | -0.0411 | -0.0127 | 0.0000 | 0.0024 | -0.0009 |  | -0.3076 | -0.3639 |
| HybridOnly_minus_DenseOnly | -0.0598 | -0.0675 | -0.0015 | -0.0175 | -0.0088 | 0.0000 | 0.0041 | 0.0054 |  | 25.8378 | 26.1637 |
| HybridGraph_minus_DenseGraph | -0.0539 | -0.0650 | -0.0033 | -0.0146 | -0.0060 | 0.0000 | 0.0027 | 0.0019 |  | 25.9236 | 26.2929 |

### unanswerable_only

| Comparison | recall@10_delta | hit@10_delta | mrr@10_delta | ndcg@10_delta | precision@10_delta | exact_match_delta | token_f1_delta | rouge_l_delta | unanswerable_accuracy_delta | total_latency_sec_delta | median_total_latency_sec_delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DenseGraph_minus_DenseOnly | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0184 | 0.0174 | 0.0300 | -0.6756 | -0.9627 |
| HybridGraph_minus_HybridOnly | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0512 | 0.0520 | 0.0900 | -0.2109 | -0.2519 |
| HybridOnly_minus_DenseOnly | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0120 | 0.0103 | 0.0000 | 25.0285 | 25.2841 |
| HybridGraph_minus_DenseGraph | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0448 | 0.0449 | 0.0600 | 25.4932 | 25.9949 |

## Recommended Files For Report

- `report_ready_summary.csv`: compact summary table.
- `delta_comparisons.csv`: graph gain and hybrid-vs-dense gain.
- `per_question_deltas.csv`: inspect which questions improved/regressed.
- `combined_e2e_cases.csv`: raw predictions and retrieved contexts for all modes.
