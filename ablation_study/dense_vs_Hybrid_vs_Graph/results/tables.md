# Ablation 2 Results Tables

These tables apply the Ablation 2 plan to the current Dense and Hybrid output
artifacts. Retrieval metrics are averaged over the 400 answerable QA cases.
Generation metrics are also reported on answerable cases unless stated
otherwise. Latency percentiles use all 500 cases.

Source artifacts:

- `../../../ablation_work/denseOnly_vs_denseGraph/results/`
- `../../../ablation_work/hybridOnly_vs_hybridGraph/hybrid_graph_eval_outputs/`

## Table 1 — Retrieval without graph expansion

`GoldInContext@10` is the same hit indicator as `Hit@10`. Context Recall@10 is
`Recall@10`. `Precision@10` uses a fixed denominator of 10, while **ID Context
Precision** uses the actual number of chunks in the final context. The latter
is important for graph variants because they return fewer than 10 chunks.

| Method | Recall@5 | Recall@10 / Context Recall | GoldInContext@10 | MRR@10 | nDCG@10 | Precision@10 | ID Context Precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense-Only | 0.3678 | 0.4855 | 0.5325 | 0.2267 | 0.2813 | 0.0580 | 0.0580 |
| Hybrid-Only | 0.3140 | 0.4257 | 0.4650 | 0.2252 | 0.2638 | 0.0493 | 0.0493 |
| Delta (Hybrid − Dense) | −0.0538 | −0.0598 | −0.0675 | −0.0015 | −0.0175 | −0.0088 | −0.0088 |

## Table 2 — Graph-augmented retrieval

| Method | Recall@5 | Recall@10 / Context Recall | GoldInContext@10 | MRR@10 | nDCG@10 | Precision@10 | ID Context Precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense + Graph | 0.3550 | 0.3615 | 0.3900 | 0.2045 | 0.2374 | 0.0425 | 0.0800 |
| Hybrid + Graph | 0.2993 | 0.3076 | 0.3250 | 0.2012 | 0.2228 | 0.0365 | 0.0641 |
| Delta (Hybrid + Graph − Dense + Graph) | −0.0557 | −0.0539 | −0.0650 | −0.0033 | −0.0146 | −0.0060 | −0.0159 |

## Table 3 — Effect of graph expansion

The graph-only and graph-missed entries count gold chunks at top-10. The
parentheses show the number and percentage of answerable queries affected.

| Base retriever | Delta Recall@10 | Delta MRR@10 | Delta nDCG@10 | Graph-only gold | Graph-missed gold | Gold moved into top-10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense: Only → +Graph | −0.1240 | −0.0222 | −0.0439 | 3 chunks (1 query, 0.25%) | 65 chunks (61 queries, 15.25%) | 3 |
| Hybrid: Only → +Graph | −0.1181 | −0.0240 | −0.0411 | 9 chunks (6 queries, 1.50%) | 60 chunks (59 queries, 14.75%) | 9 |

### Gold-chunk rank shifts after graph expansion

Ranks are compared within the top 10; a missing gold chunk is assigned rank 11.
Positive delta means that a gold chunk moved upward.

| Base retriever | Mean Δrank | Median Δrank | Moved up | Moved down | Unchanged |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | −0.4073 | 0 | 8 (1.45%) | 75 (13.64%) | 467 (84.91%) |
| Hybrid | −0.3418 | 0 | 13 (2.36%) | 71 (12.91%) | 466 (84.73%) |

There are 550 gold-chunk observations across the 400 answerable queries.

## Table 4 — Downstream quality and efficiency

Retrieval latency is the sum of embedding, dense search, BM25 search/RRF (when
applicable), and graph expansion (when applicable). Total latency includes
generation. Percentiles are calculated across all 500 cases.

| Method | Token F1 | ROUGE-L | Unanswerable Accuracy | Avg. context chunks | Retrieval p50 / p95 (s) | Total p50 / p95 (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense-Only | 0.1949 | 0.1665 | 0.3800 | 10.000 | 0.797 / 0.856 | 5.483 / 9.946 |
| Hybrid-Only | 0.1990 | 0.1719 | 0.3800 | 10.000 | 27.855 / 27.924 | 31.538 / 33.623 |
| Dense + Graph | 0.1987 | 0.1691 | 0.4100 | 5.605 | 0.798 / 0.860 | 4.998 / 9.750 |
| Hybrid + Graph | 0.2014 | 0.1710 | 0.4700 | 6.305 | 27.858 / 27.929 | 31.180 / 33.312 |

Exact Match is zero in the current summaries for all four methods and is not a
useful headline metric. LLM-judge metrics are intentionally outside the scope
of this ablation because no human-calibrated validation set is available.

## Paired win/tie/loss results

The following are paired over the same 400 answerable QA IDs. The delta is
treatment minus baseline.

| Comparison | Metric | Mean delta | Win / tie / loss |
| --- | --- | ---: | ---: |
| Dense → Hybrid | Recall@10 | −0.0598 | 25 / 318 / 57 |
| Dense → Hybrid | MRR@10 | −0.0015 | 73 / 203 / 124 |
| Dense → Hybrid | nDCG@10 | −0.0175 | 76 / 198 / 126 |
| Dense → Hybrid | Token F1 | +0.0041 | 171 / 71 / 158 |
| Dense + Graph → Hybrid + Graph | Recall@10 | −0.0539 | 38 / 296 / 66 |
| Dense + Graph → Hybrid + Graph | MRR@10 | −0.0033 | 65 / 244 / 91 |
| Dense + Graph → Hybrid + Graph | nDCG@10 | −0.0146 | 66 / 243 / 91 |
| Dense + Graph → Hybrid + Graph | Token F1 | +0.0027 | 169 / 70 / 161 |
| Dense-Only → Dense + Graph | Recall@10 | −0.1240 | 1 / 338 / 61 |
| Dense-Only → Dense + Graph | MRR@10 | −0.0222 | 0 / 339 / 61 |
| Hybrid-Only → Hybrid + Graph | Recall@10 | −0.1181 | 6 / 335 / 59 |
| Hybrid-Only → Hybrid + Graph | MRR@10 | −0.0240 | 0 / 337 / 63 |

## Paired bootstrap confidence intervals

These are percentile 95% confidence intervals for the mean per-query delta,
using 10,000 query-level bootstrap resamples of the 400 answerable QA cases.
The random seed was `20260907`.

| Comparison | Metric | Mean delta | 95% CI |
| --- | --- | ---: | ---: |
| Dense → Hybrid | Recall@10 | −0.0598 | [−0.0971, −0.0221] |
| Dense → Hybrid | MRR@10 | −0.0015 | [−0.0299, +0.0271] |
| Dense → Hybrid | nDCG@10 | −0.0175 | [−0.0437, +0.0085] |
| Dense → Hybrid | Token F1 | +0.0041 | [−0.0037, +0.0121] |
| Dense + Graph → Hybrid + Graph | Recall@10 | −0.0539 | [−0.0996, −0.0074] |
| Dense + Graph → Hybrid + Graph | MRR@10 | −0.0033 | [−0.0346, +0.0276] |
| Dense + Graph → Hybrid + Graph | nDCG@10 | −0.0146 | [−0.0457, +0.0174] |
| Dense + Graph → Hybrid + Graph | Token F1 | +0.0027 | [−0.0064, +0.0121] |
| Dense-Only → Dense + Graph | Recall@10 | −0.1240 | [−0.1562, −0.0944] |
| Dense-Only → Dense + Graph | MRR@10 | −0.0222 | [−0.0280, −0.0168] |
| Dense-Only → Dense + Graph | nDCG@10 | −0.0439 | [−0.0552, −0.0332] |
| Dense-Only → Dense + Graph | Token F1 | +0.0038 | [−0.0025, +0.0099] |
| Hybrid-Only → Hybrid + Graph | Recall@10 | −0.1181 | [−0.1513, −0.0873] |
| Hybrid-Only → Hybrid + Graph | MRR@10 | −0.0240 | [−0.0300, −0.0183] |
| Hybrid-Only → Hybrid + Graph | nDCG@10 | −0.0411 | [−0.0531, −0.0292] |
| Hybrid-Only → Hybrid + Graph | Token F1 | +0.0024 | [−0.0049, +0.0095] |

## Stratified graph analysis

The table reports treatment-minus-baseline deltas for answerable queries. The
last two columns are the percentages of queries with at least one graph-only or
graph-missed gold chunk at top-10.

| Comparison | Stratum | n | ΔRecall@10 | ΔMRR@10 | ΔnDCG@10 | Graph-only | Graph-missed |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense → Dense + Graph | easy | 285 | −0.1248 | −0.0224 | −0.0436 | 0.4% | 14.0% |
| Dense → Dense + Graph | medium | 114 | −0.1231 | −0.0218 | −0.0450 | 0.0% | 18.4% |
| Dense → Dense + Graph | hard | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0% | 0.0% |
| Hybrid → Hybrid + Graph | easy | 285 | −0.1353 | −0.0263 | −0.0463 | 1.4% | 15.8% |
| Hybrid → Hybrid + Graph | medium | 114 | −0.0760 | −0.0183 | −0.0284 | 1.8% | 12.3% |
| Hybrid → Hybrid + Graph | hard | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0% | 0.0% |
| Dense → Dense + Graph | abstractive | 199 | −0.1266 | −0.0224 | −0.0465 | 0.0% | 15.6% |
| Dense → Dense + Graph | boolean | 123 | −0.1138 | −0.0232 | −0.0413 | 0.0% | 15.4% |
| Dense → Dense + Graph | extractive | 78 | −0.1333 | −0.0201 | −0.0415 | 1.3% | 14.1% |
| Hybrid → Hybrid + Graph | abstractive | 199 | −0.1156 | −0.0216 | −0.0408 | 0.5% | 13.6% |
| Hybrid → Hybrid + Graph | boolean | 123 | −0.0894 | −0.0247 | −0.0329 | 3.3% | 13.8% |
| Hybrid → Hybrid + Graph | extractive | 78 | −0.1697 | −0.0287 | −0.0545 | 1.3% | 19.2% |

The hard stratum contains only one answerable query and should not support a
substantive conclusion.

## Scope decision

The ablation is finalized without LLM-judge metrics. Faithfulness and Answer
Relevancy are excluded rather than treated as missing evidence. The deterministic
tables, paired analysis, and bootstrap intervals above are the reportable
results for this section.
