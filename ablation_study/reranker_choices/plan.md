# Ablation 3: Reranker choices

The evaluation protocol for this ablation is maintained in
[`ablation_work/reranker_choices/metrics_plan.md`](../../ablation_work/reranker_choices/metrics_plan.md).
This folder contains the study-facing derived documentation; the frozen
six-configuration run and analysis outputs remain in
[`ablation_work/reranker_choices`](../../ablation_work/reranker_choices/).

The controlled comparison uses the same 500-question benchmark, dense and
BM25 candidate caches, `C30` RRF candidate pool, `T10` final context, generator,
prompt, and hardware settings. RRF-only is the primary baseline for the four
rerankers; None is retained as a separate fusion control.
