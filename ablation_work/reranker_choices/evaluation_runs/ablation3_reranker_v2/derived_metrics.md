# Derived Metrics: Multi-Reranker Ablation

This report implements the deterministic portions of `metrics_plan.md` against the refreshed `ablation3_reranker_v2` artifacts. Retrieval metrics use 400 answerable questions; answerability metrics use all 500 questions. The four rerankers are compared with RRF-only, the primary shared-fusion baseline. None is retained as a separate fusion control.

## 1. Validation and candidate pool

- Configurations: 6; every run contains 500 cases, including 400 answerable and 100 unanswerable questions.
- Controlled manifest settings agree across runs: **True** (`top_k=30`, `top_n=10`, `rrf_k=60`).
- Same QA-id set across configurations: **True**.
- Reconstructed RRF C30 matches recorded RRF-only T10 exactly for **500/500** cases.
- RRF parameters: `rrf_k=60`, candidate limit `C30`.
- Recomputed headline values agree with `comparison.csv` within a maximum absolute difference of **0.000050**.

The candidate pool is reconstructed from the shared dense and BM25 top-30 caches using reciprocal-rank fusion. Because the reconstruction matches the recorded RRF-only top-10 for every query, it is used as the fixed candidate pool for the retention analysis.

## 2. Table 1 — Candidate-controlled retrieval

Gold retention is conditional on at least one gold chunk being available in C30. Values are absolute metric values, not percentage points.

| Model | Candidate Recall@30 | Candidate Hit@30 | Gold retention@10 | Candidate-hit preservation@10 | nDCG@10 | Recall@10 | MRR@10 | Hit@1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 0.5995 | 0.6450 | 0.8049 | 0.8333 | 0.2714 | 0.4842 | 0.2167 | 0.1100 |
| RRF-only | 0.5995 | 0.6450 | 0.7129 | 0.7442 | 0.2728 | 0.4382 | 0.2335 | 0.1500 |
| mMiniLM | 0.5995 | 0.6450 | 0.8256 | 0.8411 | 0.3425 | 0.4973 | 0.3047 | 0.1950 |
| Qwen3 | 0.5995 | 0.6450 | 0.8702 | 0.8876 | 0.3688 | 0.5218 | 0.3418 | 0.2350 |
| BGE | 0.5995 | 0.6450 | 0.8630 | 0.8798 | 0.3593 | 0.5188 | 0.3247 | 0.2150 |
| Jina | 0.5995 | 0.6450 | 0.8850 | 0.9070 | 0.3914 | 0.5305 | 0.3670 | 0.2525 |

## 3. Table 2 — Paired effects versus RRF-only

Deltas are reranker minus RRF-only. Overall intervals use 10,000 paired-bootstrap replicates over answerable questions with the recorded seed. Win/tie/loss is treatment better / equal / baseline better.

| Reranker | Δ nDCG@10 (95% CI) | Δ Recall@10 (95% CI) | Δ MRR@10 (95% CI) | nDCG W/T/L | Recall W/T/L | MRR W/T/L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mMiniLM | +0.0696 [+0.0377, +0.1026] | +0.0591 [+0.0185, +0.0996] | +0.0712 [+0.0355, +0.1068] | 136 / 189 / 75 | 62 / 308 / 30 | 133 / 194 / 73 |
| Qwen3 | +0.0960 [+0.0652, +0.1273] | +0.0837 [+0.0457, +0.1225] | +0.1084 [+0.0724, +0.1436] | 138 / 201 / 61 | 64 / 314 / 22 | 134 / 204 / 62 |
| BGE | +0.0865 [+0.0547, +0.1184] | +0.0807 [+0.0429, +0.1180] | +0.0912 [+0.0550, +0.1270] | 138 / 192 / 70 | 63 / 315 / 22 | 136 / 198 / 66 |
| Jina | +0.1185 [+0.0846, +0.1527] | +0.0923 [+0.0551, +0.1298] | +0.1335 [+0.0951, +0.1724] | 141 / 195 / 64 | 67 / 312 / 21 | 139 / 202 / 59 |

### Paired safety effect versus RRF-only

False-refusal deltas are reranker minus RRF-only; negative values are safer because they indicate fewer unnecessary refusals. The false-answer rate is reported in Table 3 but is not bootstrapped here because the current primary paired analysis is defined over answerable cases.

| Reranker | Δ false-refusal rate (95% CI) | Win / tie / loss (lower is better) |
| --- | ---: | ---: |
| mMiniLM | +0.0025 [-0.0300, +0.0350] | 20 / 359 / 21 |
| Qwen3 | -0.0025 [-0.0325, +0.0275] | 19 / 363 / 18 |
| BGE | +0.0075 [-0.0225, +0.0375] | 17 / 363 / 20 |
| Jina | -0.0125 [-0.0400, +0.0125] | 17 / 371 / 12 |

### Paired lexical diagnostics

Token F1 and ROUGE-L are included as reproducible overlap diagnostics, not as substitutes for legal correctness or faithfulness.

| Reranker | Δ Token F1 (95% CI) | Δ ROUGE-L (95% CI) | Token F1 W/T/L | ROUGE-L W/T/L |
| --- | ---: | ---: | ---: | ---: |
| mMiniLM | +0.0150 [-0.0003, +0.0308] | +0.0153 [+0.0001, +0.0305] | 161 / 84 / 155 | 164 / 86 / 150 |
| Qwen3 | +0.0162 [+0.0012, +0.0311] | +0.0167 [+0.0017, +0.0319] | 158 / 104 / 138 | 149 / 107 / 144 |
| BGE | +0.0205 [+0.0068, +0.0342] | +0.0187 [+0.0048, +0.0332] | 175 / 91 / 134 | 168 / 92 / 140 |
| Jina | +0.0162 [+0.0023, +0.0309] | +0.0142 [-0.0005, +0.0291] | 157 / 93 / 150 | 149 / 96 / 155 |

## 4. Table 3 — Answer quality and safety

The refreshed artifacts contain lexical overlap diagnostics and a deterministic answerability signal, but no legal-judge labels, claim decomposition, or explicit citation-to-chunk mapping. The judge-dependent columns are therefore intentionally marked N/A.

| Model | Legal correctness | Completeness | Claim faithfulness | Citation precision | Citation recall | False-refusal rate | False-answer rate | Token F1 | ROUGE-L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | N/A | N/A | N/A | N/A | N/A | 18.00% | 0.00% | 0.2801 | 0.2453 |
| RRF-only | N/A | N/A | N/A | N/A | N/A | 15.75% | 0.00% | 0.2750 | 0.2416 |
| mMiniLM | N/A | N/A | N/A | N/A | N/A | 16.00% | 1.00% | 0.2901 | 0.2568 |
| Qwen3 | N/A | N/A | N/A | N/A | N/A | 15.50% | 0.00% | 0.2912 | 0.2583 |
| BGE | N/A | N/A | N/A | N/A | N/A | 16.50% | 0.00% | 0.2955 | 0.2603 |
| Jina | N/A | N/A | N/A | N/A | N/A | 14.50% | 0.00% | 0.2913 | 0.2558 |

## 5. Table 4 — Deployment trade-off

The source latency files provide means and medians but no p95 values. They also report zero sparse latency because BM25 candidates were cached, so these are not full-online BM25 timings. Peak GPU memory and per-query throughput are not recorded; observed run throughput is shown only as a reproducibility diagnostic.

| Model | Reranker p50 / p95 | Total p50 / p95 | Observed run throughput | Peak GPU memory |
| --- | ---: | ---: | ---: | ---: |
| None | 0.000 s / N/A | 2.925 s / N/A | 0.305 q/s | N/A |
| RRF-only | 0.000 s / N/A | 2.972 s / N/A | 0.304 q/s | N/A |
| mMiniLM | 0.385 s / N/A | 3.343 s / N/A | 0.281 q/s | N/A |
| Qwen3 | 9.695 s / N/A | 13.007 s / N/A | 0.075 q/s | N/A |
| BGE | 2.872 s / N/A | 5.848 s / N/A | 0.166 q/s | N/A |
| Jina | 1.278 s / N/A | 4.158 s / N/A | 0.231 q/s | N/A |

## 6. Core diagnostics

| Model | Recall@10 | MRR@10 | nDCG@10 | Token F1 | ROUGE-L | Answerability accuracy | Abstain precision | Abstain recall | Abstain F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 0.4842 | 0.2167 | 0.2714 | 0.2801 | 0.2453 | 85.60% | 58.14% | 100.00% | 73.53% |
| RRF-only | 0.4382 | 0.2335 | 0.2728 | 0.2750 | 0.2416 | 87.40% | 61.35% | 100.00% | 76.05% |
| mMiniLM | 0.4973 | 0.3047 | 0.3425 | 0.2901 | 0.2568 | 87.00% | 60.74% | 99.00% | 75.29% |
| Qwen3 | 0.5218 | 0.3418 | 0.3688 | 0.2912 | 0.2583 | 87.60% | 61.73% | 100.00% | 76.34% |
| BGE | 0.5188 | 0.3247 | 0.3593 | 0.2955 | 0.2603 | 86.80% | 60.24% | 100.00% | 75.19% |
| Jina | 0.5305 | 0.3670 | 0.3914 | 0.2913 | 0.2558 | 88.40% | 63.29% | 100.00% | 77.52% |

## 7. Slice reporting

Slice deltas are reranker minus RRF-only. CIs use the configured slice bootstrap budget (2,000 replicates). Slices with fewer than 30 questions are exploratory.

| Dimension | Slice | n | Reranker | Δ Recall@10 (95% CI) | Δ MRR@10 (95% CI) | Δ nDCG@10 (95% CI) |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| category | citation | 106 | mMiniLM | +0.0453 [-0.0491, +0.1341] | +0.0886 [+0.0022, +0.1701] | +0.0837 [+0.0062, +0.1596] |
| category | citation | 106 | Qwen3 | +0.1019 [+0.0151, +0.1962] | +0.0822 [+0.0066, +0.1536] | +0.0933 [+0.0262, +0.1583] |
| category | citation | 106 | BGE | +0.1000 [+0.0019, +0.1887] | +0.1064 [+0.0228, +0.1893] | +0.1118 [+0.0375, +0.1863] |
| category | citation | 106 | Jina | +0.1189 [+0.0282, +0.2170] | +0.1622 [+0.0786, +0.2451] | +0.1582 [+0.0751, +0.2382] |
| category | legal_validity | 91 | mMiniLM | +0.1502 [+0.0696, +0.2326] | +0.1082 [+0.0375, +0.1791] | +0.1132 [+0.0521, +0.1766] |
| category | legal_validity | 91 | Qwen3 | +0.1337 [+0.0568, +0.2125] | +0.1920 [+0.1083, +0.2752] | +0.1539 [+0.0925, +0.2186] |
| category | legal_validity | 91 | BGE | +0.1392 [+0.0678, +0.2125] | +0.1068 [+0.0333, +0.1811] | +0.1007 [+0.0446, +0.1585] |
| category | legal_validity | 91 | Jina | +0.1447 [+0.0696, +0.2143] | +0.1890 [+0.1028, +0.2726] | +0.1522 [+0.0913, +0.2150] |
| category | single_hop | 172 | mMiniLM | +0.0349 [-0.0174, +0.0892] | +0.0525 [+0.0007, +0.1039] | +0.0500 [+0.0033, +0.0965] |
| category | single_hop | 172 | Qwen3 | +0.0514 [-0.0019, +0.1076] | +0.0843 [+0.0338, +0.1342] | +0.0748 [+0.0288, +0.1208] |
| category | single_hop | 172 | BGE | +0.0349 [-0.0155, +0.0833] | +0.0783 [+0.0289, +0.1310] | +0.0648 [+0.0202, +0.1129] |
| category | single_hop | 172 | Jina | +0.0504 [-0.0000, +0.1037] | +0.0963 [+0.0434, +0.1469] | +0.0841 [+0.0381, +0.1305] |
| category | multi_hop | 20 | mMiniLM | +0.0083 [-0.0833, +0.0917] | +0.0567 [-0.0642, +0.1842] | +0.0381 [-0.0339, +0.1168] |
| category | multi_hop | 20 | Qwen3 | +0.0833 [+0.0167, +0.1667] | +0.0961 [-0.0264, +0.2381] | +0.0623 [+0.0217, +0.1066] |
| category | multi_hop | 20 | BGE | +0.1500 [+0.0417, +0.2917] | +0.1017 [-0.0467, +0.2500] | +0.1041 [+0.0323, +0.1794] |
| category | multi_hop | 20 | Jina | +0.0750 [-0.0083, +0.1750] | +0.1012 [-0.0342, +0.2433] | +0.0795 [-0.0077, +0.1798] |
| answer_type | extractive | 78 | mMiniLM | -0.0282 [-0.1179, +0.0513] | +0.0388 [-0.0514, +0.1258] | +0.0301 [-0.0497, +0.1095] |
| answer_type | extractive | 78 | Qwen3 | -0.0026 [-0.1026, +0.0897] | +0.0468 [-0.0554, +0.1459] | +0.0419 [-0.0432, +0.1300] |
| answer_type | extractive | 78 | BGE | +0.0269 [-0.0564, +0.1103] | +0.0305 [-0.0616, +0.1184] | +0.0335 [-0.0478, +0.1122] |
| answer_type | extractive | 78 | Jina | +0.0013 [-0.0885, +0.0974] | +0.0853 [-0.0090, +0.1739] | +0.0714 [-0.0133, +0.1623] |
| answer_type | abstractive | 199 | mMiniLM | +0.0846 [+0.0289, +0.1411] | +0.0647 [+0.0155, +0.1152] | +0.0700 [+0.0259, +0.1137] |
| answer_type | abstractive | 199 | Qwen3 | +0.1114 [+0.0578, +0.1663] | +0.1110 [+0.0648, +0.1566] | +0.1007 [+0.0612, +0.1428] |
| answer_type | abstractive | 199 | BGE | +0.0988 [+0.0427, +0.1541] | +0.0958 [+0.0451, +0.1497] | +0.0948 [+0.0492, +0.1411] |
| answer_type | abstractive | 199 | Jina | +0.1365 [+0.0850, +0.1880] | +0.1474 [+0.0961, +0.2014] | +0.1381 [+0.0956, +0.1871] |
| answer_type | boolean | 123 | mMiniLM | +0.0732 [-0.0000, +0.1450] | +0.1022 [+0.0432, +0.1656] | +0.0941 [+0.0397, +0.1528] |
| answer_type | boolean | 123 | Qwen3 | +0.0935 [+0.0298, +0.1558] | +0.1432 [+0.0794, +0.2072] | +0.1226 [+0.0749, +0.1741] |
| answer_type | boolean | 123 | BGE | +0.0854 [+0.0230, +0.1491] | +0.1224 [+0.0628, +0.1836] | +0.1066 [+0.0613, +0.1560] |
| answer_type | boolean | 123 | Jina | +0.0786 [+0.0163, +0.1450] | +0.1418 [+0.0764, +0.2113] | +0.1168 [+0.0627, +0.1795] |

Do not draw comparative conclusions from `multi_hop` (n=20 answerable cases), and do not promote the `hard` (n=1) or `cross_document` (n=12) groups to main evidence. The selected citation, legal-validity, and single-hop groups are larger but remain benchmark-specific.

## 8. Annotation status

A blinded template with 2,400 answerable system-question records was generated locally for the pending semantic-evaluation phase. It uses opaque system ids; the local key is stored separately for auditability. Both files are intentionally excluded from the lean commit.

The following plan metrics remain unavailable until a blinded legal annotation or validated automatic judge is supplied: legal correctness, completeness, claim faithfulness, citation precision, citation recall, and claim-faithfulness annotations for the Pareto plot. The source records store only citation counts and citation markers, not explicit citation-to-chunk mappings.

## 9. Figures

- `forest_plot.svg`: paired retrieval effects and CIs; legal correctness is shown as unavailable.
- `pareto_plot.svg`: nDCG@10 versus recorded total-latency p50; claim faithfulness is unavailable.

## Reproducibility

- Seed: `20260909`.
- Overall bootstrap replicates: `10000`.
- Slice bootstrap replicates: `2000`.
- Candidate source: local `retrieval_cache/dense_all_hits.pkl` and `retrieval_cache/bm25_all_hits.pkl` files; the raw caches are intentionally excluded from the lean commit.
- Per-configuration source: aggregate metrics and summaries under `evaluation_runs/ablation3_reranker_v2/Rerank-*/`; raw per-case files are local-only.
- This analysis measures benchmark-sampling uncertainty; it does not measure run-to-run generator randomness.
