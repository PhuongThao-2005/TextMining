# Reranker-choice ablation tables

These tables are derived from the frozen outputs in
[`ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2`](../../../ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2/).
Retrieval metrics use the 400 answerable cases. Answerability metrics use all
500 cases. The four rerankers are paired against RRF-only; None is a separate
fusion control.

## Table 1 — Candidate-controlled retrieval

Candidate Recall@30 and Candidate Hit@30 are the shared evidence ceiling. Gold
retention and candidate-hit preservation are conditional on at least one gold
chunk being present in the fixed RRF `C30` pool.

| Model | Candidate Recall@30 | Candidate Hit@30 | Gold retention@10 | Candidate-hit preservation@10 | nDCG@10 | Recall@10 | MRR@10 | Hit@1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 0.5995 | 0.6450 | 0.8049 | 0.8333 | 0.2714 | 0.4842 | 0.2167 | 0.1100 |
| RRF-only | 0.5995 | 0.6450 | 0.7129 | 0.7442 | 0.2728 | 0.4382 | 0.2335 | 0.1500 |
| mMiniLM | 0.5995 | 0.6450 | 0.8256 | 0.8411 | 0.3425 | 0.4973 | 0.3047 | 0.1950 |
| Qwen3 | 0.5995 | 0.6450 | 0.8702 | 0.8876 | 0.3688 | 0.5218 | 0.3418 | 0.2350 |
| BGE | 0.5995 | 0.6450 | 0.8630 | 0.8798 | 0.3593 | 0.5188 | 0.3247 | 0.2150 |
| Jina | 0.5995 | 0.6450 | 0.8850 | 0.9070 | 0.3914 | 0.5305 | 0.3670 | 0.2525 |

## Table 2 — Paired effects versus RRF-only

Deltas are reranker minus RRF-only. Intervals are 95% paired-bootstrap
percentile CIs from 10,000 replicates over answerable question pairs. W/T/L is
treatment better / equal / baseline better.

| Reranker | Δ nDCG@10 (95% CI) | Δ Recall@10 (95% CI) | Δ MRR@10 (95% CI) | nDCG W/T/L | Recall W/T/L | MRR W/T/L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mMiniLM | +0.0696 [+0.0377, +0.1026] | +0.0591 [+0.0185, +0.0996] | +0.0712 [+0.0355, +0.1068] | 136/189/75 | 62/308/30 | 133/194/73 |
| Qwen3 | +0.0960 [+0.0652, +0.1273] | +0.0837 [+0.0457, +0.1225] | +0.1084 [+0.0724, +0.1436] | 138/201/61 | 64/314/22 | 134/204/62 |
| BGE | +0.0865 [+0.0547, +0.1184] | +0.0807 [+0.0429, +0.1180] | +0.0912 [+0.0550, +0.1270] | 138/192/70 | 63/315/22 | 136/198/66 |
| Jina | **+0.1185 [+0.0846, +0.1527]** | **+0.0923 [+0.0551, +0.1298]** | **+0.1335 [+0.0951, +0.1724]** | 141/195/64 | 67/312/21 | 139/202/59 |

### Safety and lexical paired diagnostics

False-refusal is computed over answerable cases; negative deltas are safer.
Token F1 and ROUGE-L are overlap diagnostics only.

| Reranker | Δ false-refusal (95% CI) | False-refusal W/T/L | Δ Token F1 (95% CI) | Δ ROUGE-L (95% CI) |
| --- | ---: | ---: | ---: | ---: |
| mMiniLM | +0.0025 [-0.0300, +0.0350] | 20/359/21 | +0.0150 [-0.0003, +0.0308] | +0.0153 [+0.0001, +0.0305] |
| Qwen3 | -0.0025 [-0.0325, +0.0275] | 19/363/18 | +0.0162 [+0.0012, +0.0311] | +0.0167 [+0.0017, +0.0319] |
| BGE | +0.0075 [-0.0225, +0.0375] | 17/363/20 | +0.0205 [+0.0068, +0.0342] | +0.0187 [+0.0048, +0.0332] |
| Jina | **-0.0125 [-0.0400, +0.0125]** | 17/371/12 | +0.0162 [+0.0023, +0.0309] | +0.0142 [-0.0005, +0.0291] |

## Table 3 — Grounded-answer quality and safety

The source artifacts do not contain legal-judge labels, claim decomposition,
or explicit citation-to-chunk mappings. Those metrics are therefore reported
as N/A rather than inferred from lexical overlap or citation counts.

| Model | Legal correctness | Completeness | Claim faithfulness | Citation precision | Citation recall | False-refusal rate | False-answer rate | Token F1 | ROUGE-L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | N/A | N/A | N/A | N/A | N/A | 18.00% | 0.00% | 0.2801 | 0.2453 |
| RRF-only | N/A | N/A | N/A | N/A | N/A | 15.75% | 0.00% | 0.2750 | 0.2416 |
| mMiniLM | N/A | N/A | N/A | N/A | N/A | 16.00% | 1.00% | 0.2901 | 0.2568 |
| Qwen3 | N/A | N/A | N/A | N/A | N/A | 15.50% | 0.00% | 0.2912 | 0.2583 |
| BGE | N/A | N/A | N/A | N/A | N/A | 16.50% | 0.00% | 0.2955 | 0.2603 |
| Jina | N/A | N/A | N/A | N/A | N/A | 14.50% | 0.00% | 0.2913 | 0.2558 |

## Table 4 — Deployment trade-off

The recorded latency files provide p50 but no p95. BM25 candidates were
cached, so zero sparse latency is not full-online BM25 timing. Throughput below
is observed run throughput, not a controlled deployment benchmark; peak GPU
memory was not recorded.

| Model | Reranker p50 / p95 | Total p50 / p95 | Observed throughput | Peak GPU memory |
| --- | ---: | ---: | ---: | ---: |
| None | 0.000 s / N/A | 2.925 s / N/A | 0.305 q/s | N/A |
| RRF-only | 0.000 s / N/A | 2.972 s / N/A | 0.304 q/s | N/A |
| mMiniLM | 0.385 s / N/A | 3.343 s / N/A | 0.281 q/s | N/A |
| Qwen3 | 9.695 s / N/A | 13.007 s / N/A | 0.075 q/s | N/A |
| BGE | 2.872 s / N/A | 5.848 s / N/A | 0.166 q/s | N/A |
| Jina | 1.278 s / N/A | 4.158 s / N/A | 0.231 q/s | N/A |

## Table 5 — Requested slices

Counts are answerable cases. Slice intervals use 2,000 paired-bootstrap
replicates. Slices with fewer than 30 cases are exploratory.

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

The `hard` and `cross_document` groups are not promoted to main evidence; the
former has one case and the latter is small. The machine-readable complete
results are in [`paired_analysis.json`](../../../ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2/paired_analysis.json).
