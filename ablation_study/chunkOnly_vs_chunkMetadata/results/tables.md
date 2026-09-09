# Derived Tables

Source runs: chunk-only `20260803T065204666772Z_embed-chunkonly-dense_14eff24f`; chunk + metadata `20260803T072719927028Z_embed-chunkmeta-dense_669b3b1b`. All retrieval quantities use the paired 400 answerable questions. Deltas are chunk + metadata minus chunk-only.

## Table 1: Retrieval

| Variant | Hit@5 | Recall@5 | MRR@5 | Document Success@5 | Provision Success@5 | Hit@10 | Recall@10 | MRR@10 | Document Success@10 | Provision Success@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Chunk-only | 44.0% | 39.0% | 27.4% | 59.0% | 44.2% | 53.5% | 48.5% | 28.6% | 65.8% | 53.8% |
| Chunk + metadata | 40.2% | 36.8% | 20.9% | 61.8% | 40.2% | 53.2% | 48.5% | 22.7% | 70.2% | 53.5% |
| Delta (metadata - chunk-only) | -3.8 pp | -2.2 pp | -6.5 pp | +2.8 pp | -4.0 pp | -0.2 pp | +0.1 pp | -5.9 pp | +4.5 pp | -0.2 pp |

## Table 1: Paired Bootstrap Intervals

| Metric | Delta | Paired bootstrap 95% CI |
| --- | ---: | ---: |
| Hit@5 | -3.8 pp | [-8.8 pp, +1.2 pp] |
| Recall@5 | -2.2 pp | [-6.9 pp, +2.5 pp] |
| Mrr@5 | -6.5 pp | [-9.8 pp, -3.1 pp] |
| Document Success@5 | +2.8 pp | [-1.5 pp, +7.0 pp] |
| Provision Success@5 | -4.0 pp | [-9.0 pp, +1.2 pp] |
| Hit@10 | -0.2 pp | [-5.0 pp, +4.5 pp] |
| Recall@10 | +0.1 pp | [-4.3 pp, +4.4 pp] |
| Mrr@10 | -5.9 pp | [-9.1 pp, -2.7 pp] |
| Document Success@10 | +4.5 pp | [+0.5 pp, +8.8 pp] |
| Provision Success@10 | -0.2 pp | [-5.0 pp, +4.5 pp] |

## Paired Outcomes

| Outcome | Metadata wins | Ties | Chunk-only wins |
| --- | ---: | ---: | ---: |
| Hit@5 | 48 | 289 | 63 |
| Document Success@5 | 43 | 325 | 32 |
| Hit@10 | 47 | 305 | 48 |
| Document Success@10 | 46 | 326 | 28 |

## First Correct Rank At Top 10

Conditional mean rank among successful questions; the counts show the corresponding top-10 success totals.

| Evidence level | Chunk-only mean rank (successes) | Metadata mean rank (successes) |
| --- | ---: | ---: |
| Chunk | 3.17 (214) | 3.83 (213) |
| Provision | 3.18 (215) | 3.84 (214) |
| Document | 2.33 (263) | 2.32 (281) |

## Table 2: Downstream and Operational Context

| Variant | Token F1 | ROUGE-L | Unanswerable accuracy | Citation validity | Citation coverage | Mean total latency (ms) | P95 total latency (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Chunk-only | 24.9% | 22.0% | 82.8% | 100.0% | 90.3% | 3883.5 | 5756.6 |
| Chunk + metadata | 25.0% | 21.9% | 84.4% | 100.0% | 90.6% | 3841.8 | 5887.3 |
| Delta (metadata - chunk-only) | +0.1 pp | -0.1 pp | +1.6 pp | +0.0 pp | +0.3 pp | -41.7 | +130.7 |

Citation validity is 100.0% in both runs. Token F1 and ROUGE-L use 400 answerable questions; unanswerable accuracy uses all 500 questions; citation metrics use their source-run applicable denominators. Latency is over 500 cases.
