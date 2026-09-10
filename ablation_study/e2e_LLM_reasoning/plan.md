# End-to-End LLM Reasoning Ablation

## Purpose and scope

This folder records the study-facing results for the end-to-end LLM reasoning
ablation. The frozen run outputs remain under
[`ablation_work/e2e_LLM_Reasoning`](../../ablation_work/e2e_LLM_Reasoning/).
Only derived tables, figures, and prose are copied here.

The primary question is whether a reasoning-oriented prompt changes observable
answer behavior when the benchmark, retrieved context, and decoding settings
are held fixed. The saved outputs do not contain legal-domain annotations,
claim-level entailment labels, structured justifications, raw CoT, or
reasoning-token accounting. Therefore this study reports lexical answer
diagnostics, evidence-availability strata, template-based answerability
decisions, structural citation formatting, completion, and latency; it does
not claim semantic legal correctness, citation entailment, refusal quality, or
faithful latent reasoning.

## Controlled setup

- Benchmark: 500 Vietnamese legal QA cases (400 answerable, 100 unanswerable)
- Retrieval: top-10 multilingual-E5 dense retrieval with graph expansion, RRF
  fusion (`rrf_k=60`), and mMiniLM cross-encoder reranking
- Generation: Base versus reasoning/CoT prompt, temperature 0, maximum 1,024
  output tokens
- Primary paired comparison: GPT-4o-mini Base versus CoT, both completed on
  all 500 cases
- Other models: DeepSeek-V3.1-Thinking, GLM-5, and Qwen3-8B; complete pairs
  remain descriptive only because GPT-4o-mini is the pre-specified primary
  comparison

## Analysis protocol

The post-hoc analysis uses only the saved `e2e_predictions.jsonl`,
`e2e_metrics.json`, `latency.json`, `errors.jsonl`, and `manifest.json` files.
It computes per-question Base-to-CoT deltas, win/tie/loss counts, 95% paired
bootstrap intervals (10,000 replicates, seed 42), evidence-availability
strata, answerability confusion matrices, structural citation diagnostics,
failure reasons/stages, and generation/total p50/p95 latency.

Regenerate the derived outputs with:

```bash
python3 ../../ablation_work/e2e_LLM_Reasoning/analyze_posthoc.py \
  --root ../../ablation_work/e2e_LLM_Reasoning
```

The script writes its canonical outputs to
`ablation_work/e2e_LLM_Reasoning/posthoc_results`; copy the derived artifacts
into this folder after refreshing the frozen analysis.

## Source and implementation

- [Operative no-rerun metrics plan](../../ablation_work/e2e_LLM_Reasoning/posthoc_metrics_plan.md)
- [Full metrics design](../../ablation_work/e2e_LLM_Reasoning/metrics_plan.md)
- [Analysis implementation](../../ablation_work/e2e_LLM_Reasoning/analyze_posthoc.py)
