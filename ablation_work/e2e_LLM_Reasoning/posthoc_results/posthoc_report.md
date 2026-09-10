# Post-hoc Evaluation: LLM Reasoning Ablation

> Generated from the saved run artifacts; no model call, retrieval rerun, or new annotation was used.

## Scope and claim boundary

This report analyzes `8` saved runs under `/Users/mac/Dev/HCMUS/Text_mining/L_RAG/ablation_work/e2e_LLM_Reasoning`. The primary paired inference is GPT-4o-mini Base versus CoT; other model pairs remain descriptive, with incomplete cells and identity/provenance checks exposed below. Paired bootstrap intervals use 10,000 replicates (seed 42).

The historical outputs contain final answers, retrieval context, structural citation metadata, and lexical metrics, but no claim annotations, semantic entailment labels, structured justification, raw CoT, or reasoning-token accounting. Accordingly, this report does **not** claim legal correctness, claim faithfulness, citation entailment, refusal quality, or faithful latent reasoning.

## Data-integrity notes

The following provenance checks found naming or identity ambiguities. They are reported rather than repaired automatically:

- qwen3-8b-CoT: directory name suggests `qwen3-8b`, but the manifest/resolved config declares `deepseek-v3.1-thinking`; manifest metadata is used for analysis.
- Multiple run directories share the `deepseek-v3.1-thinking` / `CoT` identity: deepseekv3.1-thinking-CoT, qwen3-8b-CoT. The paired summary uses the lexicographically first Base/CoT directory; all runs remain in inventory and reliability outputs.

## Run inventory

| Condition | Valid / scheduled | Failures | Completion | Failure reason |
| --- | ---: | ---: | ---: | ---: |
| GPT-4o-mini / Base | 500 / 500 | 0 | 100.00% | — |
| GPT-4o-mini / CoT | 500 / 500 | 0 | 100.00% | — |
| DeepSeek-V3.1-Thinking / Base | 500 / 500 | 0 | 100.00% | — |
| DeepSeek-V3.1-Thinking / CoT | 493 / 500 | 7 | 98.60% | model unavailable: 6, rate limit: 1 |
| DeepSeek-V3.1-Thinking / CoT | 334 / 500 | 166 | 66.80% | quota: 166 |
| GLM-5 / Base | 500 / 500 | 0 | 100.00% | — |
| GLM-5 / CoT | 500 / 500 | 0 | 100.00% | — |
| Qwen3-8B / Base | 500 / 500 | 0 | 100.00% | — |

Failed generations are retained in scheduled-denominator reliability and decision views. Incomplete rows are not silently treated as lexical failures in the paired-quality tables; those tables use the exact successful answerable intersection and expose its `n`.

## 1. Primary paired comparison: GPT-4o-mini

| Metric | Base | CoT | CoT − Base | 95% paired CI | n |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact Match | 14.00% | 13.75% | -0.25 pp | [-1.50, +1.00] pp | 400 |
| Token F1 | 24.72% | 23.15% | -1.57 pp | [-2.24, -0.92] pp | 400 |
| Rouge L | 21.60% | 19.90% | -1.71 pp | [-2.34, -1.10] pp | 400 |

| Metric | CoT win | Tie | CoT loss | McNemar exact p (EM only) |
| --- | ---: | ---: | ---: | ---: |
| Exact Match | 3 (0.75%) | 393 (98.25%) | 4 (1.00%) | 1.0000 |
| Token F1 | 79 (19.75%) | 164 (41.00%) | 157 (39.25%) | — |
| Rouge L | 80 (20.00%) | 163 (40.75%) | 157 (39.25%) | — |

The exact successful answerable intersection is `n=400`; both cells are fully paired: `True`.

### Evidence-availability stratification

`context_recall@k` is used only to stratify the fixed retrieved context. It is not interpreted as a prompt-improvable outcome. The GPT pair has 0 context-recall mismatches across matched cases.

| Evidence stratum | n | Base EM | CoT EM | Δ EM | Base F1 | CoT F1 | Δ F1 | Base ROUGE-L | CoT ROUGE-L | Δ ROUGE-L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| support fully retrieved | 138 | 17.39% | 18.12% | +0.72 pp | 28.24% | 26.26% | -1.98 pp | 25.64% | 23.34% | -2.30 pp |
| partial support retrieved | 29 | 10.34% | 6.90% | -3.45 pp | 25.62% | 23.76% | -1.86 pp | 21.04% | 19.45% | -1.59 pp |
| no support retrieved | 233 | 12.45% | 12.02% | -0.43 pp | 22.53% | 21.23% | -1.30 pp | 19.29% | 17.92% | -1.37 pp |

The saved data reproduce the planned strata (fully present, partial, absent). They show observable answer behavior conditional on retrieved support, not claim-level faithfulness.

## 2. Answerability decision behavior

The saved `unanswerable_accuracy` field is relabeled here as **template-based answerability decision accuracy**. It detects answer/refusal format behavior; it is not a semantic refusal-quality measure. Clarification cannot be recovered from the historical final-answer records.

| Condition | Unanswerable recognition | Answerable non-refusal | False refusal | Overall (scheduled) | Overall (valid only) |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-4o-mini / Base | 98.00% | 78.75% | 21.25% | 82.60% | 82.60% |
| GPT-4o-mini / CoT | 98.00% | 80.50% | 19.50% | 84.00% | 84.00% |
| DeepSeek-V3.1-Thinking / Base | 100.00% | 90.00% | 10.00% | 92.00% | 92.00% |
| DeepSeek-V3.1-Thinking / CoT | 100.00% | 88.75% | 9.50% | 91.00% | 92.29% |
| DeepSeek-V3.1-Thinking / CoT | 79.00% | 55.75% | 8.00% | 60.40% | 90.42% |
| GLM-5 / Base | 98.00% | 90.25% | 9.75% | 91.80% | 91.80% |
| GLM-5 / CoT | 95.00% | 93.00% | 7.00% | 93.40% | 93.40% |
| Qwen3-8B / Base | 96.00% | 95.75% | 4.25% | 95.80% | 95.80% |

For the complete GPT pair, the answerability matrix is:

| Prompt | Gold | Answer | Refuse | Failed |
| --- | ---: | ---: | ---: | ---: |
| Base | answerable | 315 | 85 | 0 |
| Base | unanswerable | 2 | 98 | 0 |
| CoT | answerable | 322 | 78 | 0 |
| CoT | unanswerable | 2 | 98 | 0 |

## 3. Citation discipline (structural only)

Citation metrics below describe marker presence and parser coverage. They do not establish that a cited passage entails a claim.

| Condition | Valid answerable / scheduled | Citation presence | Structural coverage | Mean unique sources | Invalid / all markers |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-4o-mini / Base | 400 / 400 | 78.25% | 89.42% | 1.46 | 0 / 599 |
| GPT-4o-mini / CoT | 400 / 400 | 81.00% | 87.91% | 1.68 | 0 / 714 |
| DeepSeek-V3.1-Thinking / Base | 400 / 400 | 90.00% | 82.38% | 2.57 | 0 / 1307 |
| DeepSeek-V3.1-Thinking / CoT | 393 / 400 | 90.84% | 75.15% | 2.71 | 0 / 1365 |
| DeepSeek-V3.1-Thinking / CoT | 255 / 400 | 87.45% | 81.68% | 2.63 | 0 / 859 |
| GLM-5 / Base | 400 / 400 | 91.75% | 80.26% | 2.72 | 0 / 1555 |
| GLM-5 / CoT | 400 / 400 | 93.75% | 78.12% | 3.04 | 0 / 1754 |
| Qwen3-8B / Base | 400 / 400 | 97.75% | 65.78% | 1.79 | 5 / 877 |

## 4. Reliability and efficiency

| Condition | Valid / scheduled | Generation p50 / p95 (s) | Total p50 / p95 (s) | Failure stage |
| --- | ---: | ---: | ---: | ---: |
| GPT-4o-mini / Base | 500 / 500 | 2.92 / 5.74 | 13.99 / 17.21 | — |
| GPT-4o-mini / CoT | 500 / 500 | 3.68 / 6.17 | 14.74 / 18.42 | — |
| DeepSeek-V3.1-Thinking / Base | 500 / 500 | 7.28 / 15.51 | 16.15 / 24.55 | — |
| DeepSeek-V3.1-Thinking / CoT | 493 / 500 | 7.74 / 20.41 | 18.52 / 31.00 | generation: 7 |
| DeepSeek-V3.1-Thinking / CoT | 334 / 500 | 17.09 / 49.65 | 19.23 / 50.24 | generation: 166 |
| GLM-5 / Base | 500 / 500 | 4.17 / 8.79 | 14.29 / 19.09 | — |
| GLM-5 / CoT | 500 / 500 | 4.15 / 8.73 | 15.96 / 21.23 | — |
| Qwen3-8B / Base | 500 / 500 | 4.77 / 9.13 | 14.15 / 18.51 | — |

Token counts, provider reasoning-token metadata, and cost are not present in the saved records. The latency artifacts include means and percentiles; p50/p95 are used here to expose the long tail.

## 5. Descriptive model pairs

The following pairs are exported in `paired_metrics.csv` and `paired_group_deltas.csv`. They are not primary prompt effects unless both cells contain the same complete question set with no failures.

| Model | Base valid | CoT valid | Paired n | Δ Token F1 | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: |
| GPT-4o-mini | 500/500 | 500/500 | 400 | -1.57 pp | primary paired inference |
| DeepSeek-V3.1-Thinking | 500/500 | 493/500 | 393 | -1.35 pp | descriptive only |
| GLM-5 | 500/500 | 500/500 | 400 | -0.68 pp | descriptive only |

## Figures and machine-readable outputs

- [Paired Token-F1 delta histogram](paired_token_f1_delta.svg)
- [Win/tie/loss slice bars](win_tie_loss.svg)
- [Template decision matrix](refusal_confusion.svg)
- `posthoc_analysis.json`: complete analysis object and provenance
- `paired_case_deltas.csv`: one row per successful paired answerable case
- `paired_metrics.csv`: aggregate paired deltas and CIs
- `paired_group_deltas.csv`: category/difficulty/answer-type slices
- `evidence_strata.csv`, `answerability_decisions.csv`, `citation_metrics.csv`, `run_reliability.csv`: appendix tables

## Bounded conclusion

Under fixed retrieved context, the saved GPT-4o-mini pair characterizes observable Base-versus-CoT output behavior, including lexical deltas, template-based decision behavior, structural citation formatting, and latency. It cannot demonstrate superior or inferior latent reasoning, legal correctness, claim faithfulness, citation entailment, or refusal quality. Provider-failed and partial cells remain descriptive until rerun to completion.

Generated by `analyze_posthoc.py`; bootstrap replicates=10000, seed=42, output directory `/Users/mac/Dev/HCMUS/Text_mining/L_RAG/ablation_work/e2e_LLM_Reasoning/posthoc_results`.
