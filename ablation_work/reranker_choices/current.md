# Current Status: Multi-Reranker Ablation

## Status

**Complete experimental run; deterministic metrics analysis is implemented.**

The implementation follows [metrics_plan.md](metrics_plan.md), including
candidate-pool validation, candidate-controlled retrieval measures, paired
10,000-replicate bootstrap intervals, win/tie/loss counts, safety diagnostics,
requested slices, and dependency-free figures. Legal-judge, claim-level, and
explicit citation-mapping metrics remain pending because those labels are not
present in the source artifacts.

The refreshed `ablation3_reranker_v2` run completed on 2026-09-08. It evaluates
six hybrid-retrieval configurations on the same 500-question legal QA benchmark
(400 answerable, 100 unanswerable). Every configuration completed all 500 cases
with zero retrieval or generation errors. This supersedes the earlier partial
reranker outputs: Qwen now completes successfully and Jina is included.

## Controlled Setup

- Dense encoder: `intfloat/multilingual-e5-large`
- Generator: `gpt-4o-mini`
- Candidate pool / final context: `top_k=30`, `top_n=10`
- RRF parameter: `rrf_k=60`
- Device: CUDA
- Configurations: no reranker, RRF-only, mMiniLM CrossEncoder,
  Qwen3-Reranker-0.6B, BGE-Reranker-v2-m3, and Jina-Reranker-v2-base-multilingual

All six output files contain the same 500 `qa_id`s. Retrieval scores are
computed on the 400 answerable cases; answer scores use the applicable
answerable cases; unanswerable accuracy uses the 100 unanswerable cases.

The reconstructed RRF top-30 candidate pool is identical to the recorded
RRF-only top-10 prefix for all 500 questions. Its evidence ceiling is Candidate
Recall@30 = 0.5995 and Candidate Hit@30 = 0.6450, shared by every configuration.

## Results

| Configuration | Recall@10 | Hit@10 | MRR@10 | nDCG@10 | Token F1 | ROUGE-L | Unanswerable accuracy | Reranker latency | Total latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 0.4842 | 0.5375 | 0.2167 | 0.2714 | 0.2801 | 0.2453 | 0.856 | 0.000 s | 3.284 s |
| RRF-only | 0.4382 | 0.4800 | 0.2335 | 0.2728 | 0.2750 | 0.2416 | 0.874 | 0.000 s | 3.287 s |
| mMiniLM CrossEncoder | 0.4973 | 0.5425 | 0.3047 | 0.3425 | 0.2901 | 0.2568 | 0.872 | 0.383 s | 3.545 s |
| Qwen3-Reranker | 0.5218 | 0.5725 | 0.3418 | 0.3688 | 0.2912 | 0.2583 | 0.876 | 10.016 s | 13.397 s |
| BGE-Reranker-v2-m3 | 0.5188 | 0.5675 | 0.3247 | 0.3593 | **0.2955** | **0.2603** | 0.868 | 2.903 s | 6.007 s |
| Jina-Reranker-v2 | **0.5305** | **0.5850** | **0.3670** | **0.3914** | 0.2913 | 0.2558 | **0.884** | 1.303 s | 4.312 s |

All latencies are per-query mean stage values. Candidate artifacts are cached;
the recorded dense-stage time is included, but `sparse_latency_s` is 0.0 for
every run and therefore does not represent full online BM25 retrieval cost.

### Paired reranker effects versus RRF-only

The following deltas are computed per `qa_id`; intervals are 95% paired-bootstrap
percentile CIs from 10,000 replicates.

| Reranker | Δ nDCG@10 | Δ Recall@10 | Δ MRR@10 | Δ false-refusal rate |
| --- | ---: | ---: | ---: | ---: |
| mMiniLM | +0.0696 [+0.0377, +0.1026] | +0.0591 [+0.0185, +0.0996] | +0.0712 [+0.0355, +0.1068] | +0.0025 [-0.0300, +0.0350] |
| Qwen3 | +0.0960 [+0.0652, +0.1273] | +0.0837 [+0.0457, +0.1225] | +0.1084 [+0.0724, +0.1436] | -0.0025 [-0.0325, +0.0275] |
| BGE | +0.0865 [+0.0547, +0.1184] | +0.0807 [+0.0429, +0.1180] | +0.0912 [+0.0550, +0.1270] | +0.0075 [-0.0225, +0.0375] |
| Jina | **+0.1185 [+0.0846, +0.1527]** | **+0.0923 [+0.0551, +0.1298]** | **+0.1335 [+0.0951, +0.1724]** | **-0.0125 [-0.0400, +0.0125]** |

Jina has the largest paired retrieval gains, while none of the false-refusal
intervals excludes zero. The complete win/tie/loss counts and paired lexical
diagnostics are in [derived_metrics.md](evaluation_runs/ablation3_reranker_v2/derived_metrics.md).

## Findings

1. **Jina is the strongest retrieval configuration.** Against the primary
   RRF-only baseline, its paired gains are +9.23 percentage points Recall@10,
   +13.35 points MRR@10, and +11.85 points nDCG@10; all three bootstrap CIs are
   above zero. It also has the best observed unanswerable accuracy (0.884) and
   a 4.312 s total mean latency.

2. **BGE has the strongest downstream answer scores.** It produces the highest
   Token F1 (0.2955) and ROUGE-L (0.2603), but its total mean latency is 6.007 s.
   It is a sensible answer-quality-oriented alternative to Jina.

3. **mMiniLM is the latency-oriented option.** It adds only 0.383 s of reranking
   latency and still gives a statistically positive paired retrieval gain over
   RRF-only. Its 3.545 s total mean is the lowest among the rerankers.

4. **Qwen is no longer incomplete, but it is inefficient.** Its full 500-case
   run has no errors and provides strong retrieval scores, but Jina exceeds it
   on all headline retrieval metrics while being about 9.1 s faster per query.

5. **RRF-only is a necessary control, not a preferred answer.** It improves
   MRR@10 slightly over None (0.2335 vs. 0.2167), but lowers Recall@10 (0.4382
   vs. 0.4842), Token F1, and ROUGE-L. The fixed C30 analysis shows that the
   rerankers differ mainly in how well they retain available gold evidence:
   Jina retains 0.8850 of available gold chunks versus 0.7129 for RRF-only.

## Recommendation

- Treat **Jina-Reranker-v2** as the current retrieval/latency leader, subject to
  confirmation with legal-correctness and faithfulness labels.
- Use **BGE-Reranker-v2-m3** when the observed lexical answer diagnostics are
  preferred; it has the highest Token F1 and ROUGE-L but costs more latency.
- Use **mMiniLM CrossEncoder** for the lowest-latency reranker option.

## Remaining Work Before Report Finalization

- Collect blinded legal-correctness, completeness, claim-faithfulness, and
  citation-mapping labels (or validate an automatic judge) before making
  grounded-answer claims.
- Obtain per-query full-online latency p95, peak GPU memory, and deployment
  throughput. The current sparse stage is cached (`sparse_latency_s=0.0`), so
  the recorded p50 values are not full-online BM25 timings.
- Record the exact fusion implementation for the `None` and `RRF-only`
  controls in the experiment-methods section.
- Optionally run the planned C10/C30/C50/C100 candidate-pool sweep.
- Integrate the generated tables and figures into the formal ablation report,
  keeping conclusions bounded to this benchmark, index, prompt, and fixed
  top-30-to-top-10 setup.

## Source Artifacts

- Aggregate comparison: `evaluation_runs/ablation3_reranker_v2/comparison.csv`
- Run summary: `evaluation_runs/ablation3_reranker_v2/summary.json`
- Derived metrics, paired CIs, and slices:
  `evaluation_runs/ablation3_reranker_v2/derived_metrics.md`
- Machine-readable analysis:
  `evaluation_runs/ablation3_reranker_v2/paired_analysis.json`
- Figures: `evaluation_runs/ablation3_reranker_v2/forest_plot.svg` and
  `evaluation_runs/ablation3_reranker_v2/pareto_plot.svg`
- Blinded annotation template and key are generated locally for the pending
  semantic-evaluation phase; they are intentionally excluded from the lean
  commit.
- Per-configuration manifests, aggregate metrics, and latency summaries:
  `evaluation_runs/ablation3_reranker_v2/Rerank-*/`
- Per-case outputs and cached shared Dense/BM25 candidates remain local source
  artifacts and are intentionally excluded from the lean commit.
