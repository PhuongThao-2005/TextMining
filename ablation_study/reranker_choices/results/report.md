# Ablation 3: Multi-Reranker Choices

**Status:** Deterministic evaluation finalized; semantic legal-answer
annotation and full-online tail-latency measurements remain pending.

## Scope and controlled setup

This analysis compares six configurations on the same 500-question Vietnamese
legal QA benchmark: 400 answerable and 100 unanswerable questions. Every run
completed all 500 cases with zero retrieval or generation errors, and all six
per-case files contain the same `qa_id` set.

The shared setup is:

- Dense encoder: `intfloat/multilingual-e5-large`
- Hybrid retrieval with the recorded `rrf_k=60` setting
- Fixed RRF candidate pool of 30 chunks (`C30`) and final context of 10 (`T10`)
- Generator: `gpt-4o-mini`
- CUDA evaluation device, with common manifest settings across runs
- Configurations: None, RRF-only, mMiniLM CrossEncoder, Qwen3-Reranker,
  BGE-Reranker-v2-m3, and Jina-Reranker-v2

RRF-only is the primary paired baseline for mMiniLM, Qwen3, BGE, and Jina.
None is a separate control for the effect of the fusion/reranking decision.
The reconstructed RRF `C30` pool agrees with the recorded RRF-only `T10`
prefix for 500/500 questions.

## Findings

### Candidate evidence is fixed across configurations

The shared candidate pool has Candidate Recall@30 = **0.5995** and Candidate
Hit@30 = **0.6450**. These values are identical for every configuration, so the
reranker comparison measures promotion and retention of evidence already
available in `C30`; it does not compare different candidate-retrieval ceilings.

Jina retains 0.8850 of the available gold chunks at `T10`, compared with 0.7129
for RRF-only. Candidate-controlled values and the complete slice tables are in
[`tables.md`](tables.md).

### Jina leads the paired retrieval comparison

Relative to RRF-only, Jina improves nDCG@10 by **+0.1185** (95% CI
`[+0.0846, +0.1527]`), Recall@10 by **+0.0923** (`[+0.0551, +0.1298]`), and
MRR@10 by **+0.1335** (`[+0.0951, +0.1724]`). Each interval excludes zero. Jina
also has the strongest absolute retrieval scores: Recall@10 0.5305, MRR@10
0.3670, and nDCG@10 0.3914.

Qwen3 and BGE also show positive paired retrieval intervals, while mMiniLM is
the lower-latency reranker. The aggregate and paired results should be read
together because the primary question is ranking quality at a fixed candidate
pool, not a single composite score.

### Answer overlap and safety are secondary diagnostics

BGE has the highest observed Token F1 (0.2955) and ROUGE-L (0.2603). Jina has
the best deterministic unanswerable accuracy (0.884) and the lowest
false-refusal rate (14.50%); its false-refusal paired interval versus RRF-only
is `[-0.0400, +0.0125]`, so a safety improvement is not statistically decisive.
All six false-answer rates are between 0% and 1% in these artifacts.

The false-refusal/answerability numbers use an accent-insensitive refusal-marker
classifier. They are reproducible safety diagnostics, not legal-correctness or
faithfulness judgments.

### Latency trade-off

The reranker-stage p50 values are 0.385 s for mMiniLM, 1.278 s for Jina, 2.872
s for BGE, and 9.695 s for Qwen3. Total p50 values are 3.343 s, 4.158 s,
5.848 s, and 13.007 s respectively. These runs have `sparse_latency_s=0.0`
because the BM25 candidates were cached; therefore they must not be described
as full-online BM25 latency. p95 latency, peak GPU memory, and deployment
throughput were not recorded.

## Conclusion

For this benchmark and fixed `C30` → `T10` setup, Jina is the current
retrieval/latency leader. BGE is the answer-overlap leader, and mMiniLM is the
lowest-latency reranker. These are conditional engineering recommendations,
not a final legal-answer quality decision: legal correctness, completeness,
claim faithfulness, citation precision, and citation recall require blinded
annotations or a validated automatic judge that is absent from the source run.

## Limitations and next steps

- The generated analysis reports legal-judge and citation-mapping metrics as
  N/A rather than inferring them from lexical overlap or citation counts.
- The blinded annotation template contains 2,400 answerable
  system-question records and is generated locally; it is intentionally
  excluded from the lean commit with the raw source outputs.
- The current slice counts are answerable-only: citation 106, legal-validity
  91, single-hop 172, multi-hop 20, extractive 78, abstractive 199, and
  boolean 123. Multi-hop is exploratory because it has fewer than 30 cases.
- Remaining work is to collect/validate semantic annotations, measure
  full-online p95 latency and deployment memory/throughput, document the exact
  fusion implementation, optionally run the C10/C30/C50/C100 sweep, and
  integrate the results into the formal report.

## Source and derived artifacts

- [Current working status](../../../ablation_work/reranker_choices/current.md)
- [Metrics plan](../../../ablation_work/reranker_choices/metrics_plan.md)
- [Full derived report](../../../ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2/derived_metrics.md)
- [Machine-readable paired analysis](../../../ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2/paired_analysis.json)
- [Paired-effect forest plot](../../../ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2/forest_plot.svg)
- [Latency Pareto plot](../../../ablation_work/reranker_choices/evaluation_runs/ablation3_reranker_v2/pareto_plot.svg)
- The blinded annotation template and key are local evaluation artifacts and
  are intentionally excluded from the lean commit.
